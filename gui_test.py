import multiprocessing as mp, time
from app import App
import tkinter as tk
if __name__=='__main__':
    mp.freeze_support(); root=tk.Tk(); root.withdraw(); app=App(root)
    def wait():
        until=time.monotonic()+15
        while app.busy and time.monotonic()<until: root.update(); time.sleep(.05)
        assert not app.busy
    app.run('all'); wait(); assert 'SURP' in app.zpl
    app.editor.delete('1.0','end'); app.editor.insert('1.0','x=8\n# %% second\nprint(x)\n')
    app.editor.mark_set('insert','1.0'); app.run('cell'); wait()
    app.editor.mark_set('insert','3.0'); app.run('cell'); wait(); assert '8' in app.logs.get('1.0','end')
    app.editor.tag_add('sel','3.0','3.8'); app.run('selection'); wait()
    snapshot=app.editor.get('1.0','end-1c'); app.pending=(snapshot,'1.0','1.3','x=9'); app.apply(); assert app.editor.get('1.0','1.end')=='x=9'
    app.editor.edit_undo(); assert app.editor.get('1.0','1.end')=='x=8'
    app.close(); print('GUI logic passed')
