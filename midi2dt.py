#!/usr/bin/env python
# Requiere xdotool, python3-tk
import subprocess
import threading
import queue
import logging
import json
import sys
try:
    import Tkinter as tk
    import tkFont
    import ttk
except ImportError:  # Python 3
    import tkinter as tk
    import tkinter.font as tkFont
    import tkinter.ttk as ttk


class MidiKeyboard(object):
    def __init__(self, device=None, *args, **kwargs):
        self._device = device
        self._running = threading.Event()
        self._queue = queue.Queue()
        self.start_thread(device)

    def start_thread(self, device=None):
        if device is None:
            if self._device is None:
                return
            device = self._device
        else:
            self._device = device
        # TODO: Check if the device exists
        try:
            self._thread = threading.Thread(target=self._read_device,args=(self._queue, device))
            self._thread.setDaemon(True)
            self._thread.start()
        except Exception:
            print("Exception!", sys.exc_info()[2])
            pass

    def stop_thread(self):
        logging.info('Stop midi-thread request')
        if self._running.is_set():
            logging.debug('setting running flag off...')
            self._running.clear()
            logging.debug('closing pipe...')
            #~ self._device_pipe.stdout.close()
            self._device_pipe.kill()
            self._device_pipe.stdout.close()
            self._thread.join(1)
            logging.debug('Midi-thread closed')

    def _read_device(self, queue, device):
        self._device_pipe = subprocess.Popen(['cat', device], stdout=subprocess.PIPE, bufsize=0)
        message = []
        expected_length = -1
        self._running.set()
        data = None
        with self._device_pipe.stdout:
            while self._running.is_set():
                #~ Command  Meaning                # parameters  param 1       param 2
                #~ 0x80     Note-off                     2       key           velocity
                #~ 0x90     Note-on                      2       key           veolcity
                #~ 0xA0     Aftertouch                   2       key           touch
                #~ 0xB0     Continuous controller        2       controller #  controller value
                #~ 0xC0     Patch change                 2       instrument #
                #~ 0xD0     Channel Pressure             1       pressure
                #~ 0xE0     Pitch bend                   2       lsb (7 bits)   msb (7 bits)
                #~ 0xF0     (non-musical commands)
                try:
                    data = ord(self._device_pipe.stdout.read(1))
                    if data is not None and data >= 0x80: # status message
                        message = []
                        if data < 0xC0: # Note-off, Note-on, Aftertouch and Continuous controller
                            expected_length = 3
                        else:
                            expected_length = -1
                except:
                    if data is not None:
                        logging.error("Midi message not understood: %s - %s", hex(data), message)
                    else:
                        logging.error("Midi message was NONE")
                    expected_length = -1
                    data = None

                if expected_length:
                    message.append(data)
                    if len(message) >= expected_length:
                        queue.put(message)
                        expected_length = -1

    def read(self):
        try:
            return self._queue.get(False)
        except:
            return False

    def is_running(self):
        return self._running.is_set()

    def set_device(self, device=None):
        if device is not None:
            self._device = device


class TkWindow(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.parent.bind('<KeyPress>', self.onKeyPress)
        #~ self.midikb = MidiKeyboard()
        self.midikb = None
        self._midi_key_list = []
        self._midi_key_values = {}
        self._programming_mode = tk.IntVar()
        self._tree_selection = None
        self.initUI()
        self.read_configs()
        if len(self._cbox_device.get()):
            self.connect_to_device()

    def initUI(self):
        self.parent.title("midi2dt")
        self.pack(fill="both", expand=True)

        frame1 = ttk.Frame(self)
        frame1.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        frame1_1 = ttk.Frame(frame1)
        frame1_1.pack(side="top", fill="both", expand=True)
        frame1_2 = ttk.Frame(frame1)
        frame1_2.pack(side="bottom", fill="both", expand=False)

        frame2 = ttk.Frame(self)
        frame2.pack(side="right", fill="y", expand=False, padx=5, pady=5)

        tree_headers = [('Type',30), ('Key ID',10), ('Modifier',10), ('Key',90)]
        self._tree = ttk.Treeview(frame1_1, columns=[name for name, _ in tree_headers], show="headings", height=20)#, selectmode='browse')
        self._tree.pack(side='left', fill='both', expand=True)
        #~ self._tree.bind('<Button-1>', self.selected_item)
        self._tree.bind('<<TreeviewSelect>>', self.selected_item)
        for column, width in tree_headers:
            self._tree.heading(column, text=column)
            self._tree.column(column, width=tkFont.Font().measure(column)+width, anchor='center')

        vsb = ttk.Scrollbar(frame2, orient="vertical", command=self._tree.yview)
        vsb.pack(side='right', fill='y')
        self._tree.configure(yscrollcommand=vsb.set)

        check = ttk.Checkbutton(frame1_2, text='Programming mode', variable=self._programming_mode)
        check.pack(side='left', padx=5, pady=5)
        self._cbox_device = tk.StringVar()
        #~ device_options = subprocess.check_output('find /dev/ -name *midi*'.split())
        device_options = subprocess.check_output('find /dev/ -type d ! -perm -g+r,u+r,o+r -prune -o -name *midi* -print'.split())
        cbox = ttk.Combobox(frame1_2, textvariable=self._cbox_device, values=device_options)
        cbox.pack(side='bottom', padx=5, pady=5)
        cbox.set(device_options.split()[0])

        button = ttk.Button(frame1_2, text='Save configs', command=self.save_configs)
        button.pack(side='right', padx=5, pady=5)
        button = ttk.Button(frame1_2, text='Connect to device', command=self.connect_to_device)
        button.pack(side='right', padx=5, pady=5)
        # TODO: «programming mode»->True as default when no configuration has been set
        self._programming_mode.set(0)

    def connect_to_device(self):
        self.midikb = MidiKeyboard(self._cbox_device.get())

    def read_configs(self, file_format="json", file_name='configs.json'):
        try:
            with open(file_name, "r") as f:
                options = json.load(f)
            for line in options:
                line["tags"][0] = int(line['tags'][0],16)
                self._midi_key_list.append(line["tags"][0])
                self._tree.insert('', 'end', line["tags"][0],
                    values=line["values"], tags=line["tags"][0])
        except Exception:
            self._programming_mode.set(1)

    def save_configs(self, file_format="json", file_name='configs.json'):
        if file_format=='json':
            options = []
            for child in self._tree.get_children():
                key = self._tree.item(child)
                key["tags"][0] = hex(key["tags"][0])
                options.append(key)
            with open(file_name, "w") as f:
                json.dump(options, f, sort_keys=True, indent=4)

    def send_keystroke(self, midikey):
        key = ((midikey[0]<<4)&0xF00)|midikey[1] # To get the keyid

        #To have two values for Continouos controller, increasing and decreasing
        if (key>>8) == 0xB:
            if str(key) in self._midi_key_values.keys():
                if (midikey[2] == 0) or (midikey[2] < self._midi_key_values[str(key)]): # Zero and/or decreasing
                    key = (key<<1)|0x0
                else: # Increasing
                    key = (key<<1)|0x1
                self._midi_key_values[str(key>>1)] = midikey[2]
            else:
                self._midi_key_values[str(key)] = midikey[2]
                return

        if self._tree.exists(key):
            modifier = self._tree.item(key, option="values")[2]
            value = self._tree.item(key, option="values")[3]
            if value == "<<Undefined>>":
                return
            if len(modifier):
                value = "{}{}".format(modifier, value)
            subprocess.Popen(["xdotool", "key", value])

    def sort_treeview(self, column=0, reverse=False):
        new_treeview = [(self._tree.set(child, column), child) for child in self._tree.get_children('')]
        new_treeview.sort(reverse=reverse)

        # rearrange items in sorted positions
        for index, (_, child) in enumerate(new_treeview):
            self._tree.move(child, '', index)

    def selected_item(self, tree_item):
        self._tree_selection = self._tree.selection()

    def add_keys_availables(self, midikey=None, tags=None, values=None):
        key_type = midikey>>8
        key_note = str((midikey&0xFF))
        if key_type == 0x9:
            self._tree.insert('', 'end', midikey, tags=midikey, values="{} {} {} {}".format("Note-on", key_note, "-", "<<Undefined>>"))
        elif key_type == 0xB:
            self._tree.insert('', 'end', (midikey<<1)|1, tags=(midikey<<1)|1, values="{} {} {} {}".format("CC", key_note+"+", "-", "<<Undefined>>"))
            self._tree.insert('', 'end', (midikey<<1)|0, tags=(midikey<<1)|0, values="{} {} {} {}".format("CC", key_note+"-", "-", "<<Undefined>>"))
        self.sort_treeview()

    def onKeyPress(self, event):
        if not self._programming_mode.get():
            return
        #~ Mask     Modifier         Binary
        #~ 0x0001  Shift.           b0000 0001
        #~ 0x0002  Caps Lock.       b0000 0010
        #~ 0x0004  Control.         b0000 0100
        #~ 0x0008  Left-hand Alt.   b0000 1000
        #~ 0x0010  Num Lock.        b0001 0000
        #~ 0x0020  ???              b0010 0000
        #~ 0x0040  Windows key      b0100 0000
        #~ 0x0080  Right-hand Alt.  b1000 0000
        #~ 0x0100  Mouse button 1.
        #~ 0x0200  Mouse button 2.
        #~ 0x0400  Mouse button 3.
        if self._tree_selection is not None and len(self._tree_selection)>0:
            key = event.__dict__['keysym']
            if "Control" in key or "Alt" in key or  "Shift" in key or "Caps_Lock" in key or "Super" in key:
                return

            state = event.__dict__['state']
            modifier = ""
            if state&(1<<2):
                modifier = "Ctrl+"
            if state&(1<<3) or state&(1<<7):
                modifier = modifier+"Alt+"
            if state&(1<<0):
                modifier = modifier+"Shift+"
            if state&(1<<6):
                modifier = modifier+"Super+"

            for child in self._tree.get_children():
                if key == self._tree.item(child, option="values")[2]:
                    self._tree.set(child, 3, "<<Undefined>>")

            self._tree.set(self._tree_selection, 2, modifier)
            self._tree.set(self._tree_selection, 3, key)
            next = self._tree.next(self._tree_selection)
            self._tree.selection_set(next)
            if next == '':
                self._tree_selection = None

    def update_keys_list(self, code):
        if code not in self._midi_key_list:
            self._midi_key_list.append(code)
            self.add_keys_availables(code)
            return

    def check_midi_device(self):
        if self.midikb is not None and self.midikb.is_running():
            self.after(5, self.check_midi_device)
        else:
            self.after(1000, self.check_midi_device)
            return
        command = self.midikb.read()
        if command:
            # Only pay attention to 0x9X Note on and 0xBX Continuous controller
            key = (command[0] >> 4)
            if key == 0x9 or key == 0xB:
                key = ((key<<8)|command[1])
            else:
                return

            if (self._programming_mode.get()):
                if (command[0] >> 4) == 0xB:
                    key = key<<1
                self.update_keys_list(key)
                try: 
                    movement = float((self._tree.index(key)-5)/len(self._tree.get_children()))
                    self._tree.yview('moveto' , movement)
                    self._tree.selection_set(key)
                except Exception:
                    logging.info("""

Could not find key: "%s" in config!
please add an entry with a "tags" value of "%s"

and another one with "%s" for the positive direction's key binding
                    """, hex(key), hex(key), hex(key+1))
            else:
                self.send_keystroke(command)
            logging.debug('Key: %s %s', hex(key), hex(command[2]))

    def on_closing(self):
        logging.debug('User want to close the app')
        self.midikb.stop_thread()
        self.parent.destroy()
        logging.debug('Thanks for using this app :)')



def main():
    #~ logging.basicConfig(level=logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    #~ root.geometry("400x300")
    app = TkWindow(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.after(500, app.check_midi_device)
    root.mainloop()

if __name__ == '__main__':
    main()
