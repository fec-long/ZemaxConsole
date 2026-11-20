"""Python -> ZPL prototype. Standard library only; no ZOS-API."""
import contextlib
import io
import math
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Surface:
    radius: float
    thickness: float
    diameter: float
    glass: str = ""


def number(value, name, minimum=None):
    v = float(value)
    if not math.isfinite(v) or (minimum is not None and v < minimum):
        raise ValueError(f"{name}: invalid value {value!r}")
    return v


class Model:
    def __init__(self):
        self.surfaces = []

    def add_lens(self, radius1, radius2, thickness, diameter, glass="N-BK7"):
        """Lengths in mm. radius=0 or +/-inf denotes a plane."""
        radii = [float(radius1), float(radius2)]
        if any(math.isnan(r) for r in radii):
            raise ValueError("Radius cannot be NaN")
        radii = [0.0 if math.isinf(r) else r for r in radii]
        t = number(thickness, "thickness", 0)
        d = number(diameter, "diameter", 0)
        if t == 0 or d == 0:
            raise ValueError("Lens thickness and diameter must be positive")
        if not isinstance(glass, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", glass):
            raise ValueError("Use an ASCII glass catalogue name, e.g. N-BK7")
        sags = []
        for r in radii:
            if r and abs(r) < d / 2:
                raise ValueError("Semi-diameter exceeds spherical radius")
            sags.append(0 if not r else math.copysign(abs(r) - math.sqrt(r*r-d*d/4), r))
        if t + sags[1] - sags[0] <= 0:
            raise ValueError("Lens surfaces intersect at the specified diameter")
        self.surfaces.extend([Surface(radii[0], t, d, glass), Surface(radii[1], 0, d)])
        return (len(self.surfaces)-1, len(self.surfaces))

    def add_space(self, thickness):
        """Add air distance after the last lens; does not insert a dummy surface."""
        if not self.surfaces:
            raise ValueError("Call add_lens before add_space")
        self.surfaces[-1].thickness += number(thickness, "air space", 0)

    def zpl(self):
        if not self.surfaces:
            raise ValueError("Model is empty")
        # User supplies a NEW sequential model: OBJ=0, STOP=1, IMA=2.
        # Reuse STOP=1 as the first refracting surface, insert before IMA.
        lines = ["! ZemaxConsole 0.1 - experimental basic ZPL", 
                 "! Run ONLY in a fresh sequential model, units mm.",
                 "! Glass catalogue, wavelength and system aperture are set manually.",
                 "IF (NSUR() == 2)"]
        for i in range(2, len(self.surfaces)+1):
            lines.append(f"INSERT {i}")
        for i, s in enumerate(self.surfaces, 1):
            curvature = 0 if s.radius == 0 else 1/s.radius
            lines += [f'SURP {i}, 0, "STANDARD"',
                      f"SURP {i}, 2, {curvature:.15g}",
                      f"SURP {i}, 3, {s.thickness:.15g}",
                      f'SURP {i}, 4, "{s.glass}"',
                      f"SURP {i}, 6, {s.diameter/2:.15g}"]
        lines += ["UPDATE", 'PRINT "ZemaxConsole: surfaces written. Check LDE and glass names."',
                  "ELSE", 'PRINT "Aborted: open a NEW sequential model (OBJ, STOP, IMA)."', "ENDIF"]
        return "\n".join(lines)+"\n"


DEMO = '''# 所有长度单位：mm。每次运行从空的 Python 模型开始。
# 运行不会连接 Zemax；成功后点击“导出 ZPL”。
add_lens(radius1=50, radius2=-50,
         thickness=5, diameter=25, glass="N-BK7")
add_space(45)  # 后表面至像面的距离；这里只是演示，未自动对焦
print("已生成一片双凸透镜")
'''


def build(source):
    model = Model()
    output = io.StringIO()
    namespace = {"add_lens": model.add_lens, "add_space": model.add_space,
                 "math": math, "__name__": "__console__"}
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        exec(compile(source, "<console>", "exec"), namespace)
    return model, model.zpl(), output.getvalue()


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("ZemaxConsole 0.1 | Python → ZPL | 无 API")
    root.geometry("1100x800")
    root.minsize(800, 600)
    toolbar = ttk.Frame(root, padding=8)
    toolbar.pack(fill="x")
    status = tk.StringVar(value="离线生成器 · 序列模式 · 基础兼容配置（Zemax 版本尚未实测）")
    ttk.Label(root, textvariable=status, padding=5).pack(fill="x")
    panes = ttk.Panedwindow(root, orient="vertical")
    panes.pack(fill="both", expand=True, padx=8)
    editor = ScrolledText(panes, undo=True, font=("Consolas", 11), height=16)
    editor.insert("1.0", DEMO)
    panes.add(editor, weight=3)
    tabs = ttk.Notebook(panes)
    panes.add(tabs, weight=2)
    preview = ScrolledText(tabs, font=("Consolas", 10), state="disabled")
    table = ttk.Treeview(tabs, columns=("surface", "radius", "thickness", "glass", "semi"), show="headings")
    for key, label in zip(table["columns"], ("面号", "曲率半径 mm", "到下一面厚度 mm", "面后材料", "半口径 mm")):
        table.heading(key, text=label)
        table.column(key, width=140)
    logs = ScrolledText(tabs, font=("Consolas", 10), state="disabled")
    tabs.add(preview, text="ZPL 预览")
    tabs.add(table, text="曲面表")
    tabs.add(logs, text="输出 / 报错")
    ttk.Label(root, text="仅执行自己信任的 Python 代码；这是普通 Python 执行环境，不是沙箱。", padding=7).pack(fill="x")
    state = {"source": None, "zpl": None}

    def replace(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def run(event=None):
        source = editor.get("1.0", "end-1c")
        state.update(source=None, zpl=None)
        replace(preview, "")
        for item in table.get_children():
            table.delete(item)
        try:
            model, zpl, output = build(source)
            state.update(source=source, zpl=zpl)
            replace(preview, zpl)
            for i, s in enumerate(model.surfaces, 1):
                table.insert("", "end", values=(i, s.radius or "Infinity", s.thickness, s.glass or "AIR", s.diameter/2))
            replace(logs, output + "\n生成成功；尚未在 Zemax 中执行。\n")
            status.set(f"生成成功：{len(model.surfaces)} 个折射面；可导出 ZPL。")
            tabs.select(preview)
            return True
        except Exception:
            replace(logs, traceback.format_exc())
            status.set("生成失败；请查看报错。旧的导出结果已清除。")
            tabs.select(logs)
            return False

    def export():
        if state["source"] != editor.get("1.0", "end-1c"):
            if not run():
                return
        path = filedialog.asksaveasfilename(defaultextension=".ZPL", initialfile="ConsoleLens.ZPL", filetypes=[("ZPL macro", "*.ZPL")])
        if path:
            try:
                Path(path).write_bytes(state["zpl"].replace("\n", "\r\n").encode("ascii"))
                messagebox.showinfo("已导出", "请在 Zemax 中新建空白序列系统，单位设为 mm，\n再通过宏菜单运行此文件。\n\n"+path)
            except OSError as exc:
                messagebox.showerror("保存失败", str(exc))

    def save():
        path = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python", "*.py")])
        if path:
            try:
                Path(path).write_text(editor.get("1.0", "end-1c"), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("保存失败", str(exc))

    def load():
        path = filedialog.askopenfilename(filetypes=[("Python", "*.py")])
        if path:
            if not messagebox.askyesno("打开脚本", "替换当前编辑区？未保存的编辑将丢失。"):
                return
            try:
                source = Path(path).read_text(encoding="utf-8-sig")
                editor.delete("1.0", "end")
                editor.insert("1.0", source)
                state.update(source=None, zpl=None)
                replace(preview, "")
                for item in table.get_children():
                    table.delete(item)
                status.set("脚本已打开，尚未运行。")
            except (OSError, UnicodeError) as exc:
                messagebox.showerror("打开失败", str(exc))

    for label, action in [("运行 / F5", run), ("导出 ZPL", export), ("打开 Python", load), ("保存 Python", save)]:
        ttk.Button(toolbar, text=label, command=action).pack(side="left", padx=4)
    root.bind("<F5>", run)
    root.mainloop()


if __name__ == "__main__":
    main()
