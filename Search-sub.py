import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import queue
import sqlite3

class SearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 برنامج البحث عن مجلدات")
        self.root.geometry("650x450")
        self.root.configure(bg="#2E2E2E")

        self.folder_path = r"E:\arabic\arabic subtitles"
        self.searching = False
        self.stop_event = threading.Event()

        self.conn = sqlite3.connect("cache.db")
        self.cursor = self.conn.cursor()
        self.create_table()

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background="#2E2E2E", foreground="white", font=('Segoe UI', 12))
        style.configure('TButton', font=('Segoe UI', 11), padding=6)
        style.configure('TEntry', font=('Segoe UI', 12))

        self.title_label = ttk.Label(root, text=":أدخل اسم العمل للبحث")
        self.title_label.pack(pady=(20, 10))

        self.entry = ttk.Entry(root, width=40)
        self.entry.pack(pady=10)
        self.entry.bind('<KeyRelease>', self.on_key_release)  # حدث تحديث البحث أثناء الكتابة

        self.search_btn = ttk.Button(root, text="🔎 ابحث", command=self.on_search_button)
        self.search_btn.pack(pady=10)

        self.status_label = ttk.Label(root, text="")
        self.status_label.pack(pady=5)

        frame = ttk.Frame(root)
        frame.pack(pady=10, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(frame, width=80, height=15, yscrollcommand=self.scrollbar.set, font=('Segoe UI', 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.listbox.yview)

        self.listbox.bind('<Double-1>', self.open_folder)

        self.copy_btn = ttk.Button(root, text="📋 انسخ المسار المحدد", command=self.copy_path)
        self.copy_btn.pack(pady=(5, 15))

        self.queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                keyword TEXT,
                folder_path TEXT
            )
        ''')
        self.conn.commit()

    def get_cache(self, keyword):
        self.cursor.execute("SELECT folder_path FROM cache WHERE keyword LIKE ?", (keyword.lower() + '%',))
        results = self.cursor.fetchall()
        return [row[0] for row in results]

    def on_search_button(self):
        # لمن تضغط زر البحث، يعمل بحث كامل للكلمة كاملة
        keyword = self.entry.get().strip()
        if not keyword:
            messagebox.showwarning("تحذير", "من فضلك أدخل اسم العمل.")
            return
        if self.searching:
            self.stop_event.set()
            self.search_btn.config(text="🔎 ابحث")
            self.status_label.config(text="❌ تم إيقاف البحث.")
            self.searching = False
            return

        self.listbox.delete(0, tk.END)
        self.status_label.config(text="⏳ جاري البحث...")
        self.search_btn.config(text="🗑️ إيقاف البحث")
        self.searching = True
        self.stop_event.clear()
        threading.Thread(target=self.search_files, args=(keyword,), daemon=True).start()

    def on_key_release(self, event):
        # هذا الحدث يحدث بعد كل حرف تكتبه
        keyword = self.entry.get().strip()
        if keyword == '':
            self.listbox.delete(0, tk.END)
            self.status_label.config(text="")
            return

        # نجيب النتائج اللي تبدأ بالكلمة اللي كتبتها من الكاش (أسرع)
        cached_results = self.get_cache(keyword)
        self.listbox.delete(0, tk.END)
        if cached_results:
            self.status_label.config(text=f"🗂 عرض النتائج من الذاكرة المؤقتة: {len(cached_results)} مجلد.")
            self.display_results(cached_results)
        else:
            self.status_label.config(text="لا توجد نتائج في الذاكرة المؤقتة. اضغط بحث لإيجاد النتائج.")

    def search_files(self, keyword):
        conn = sqlite3.connect("cache.db")
        cursor = conn.cursor()

        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        results = []
        try:
            for name in os.listdir(self.folder_path):
                if self.stop_event.is_set():
                    break
                full_path = os.path.join(self.folder_path, name)
                if os.path.isdir(full_path) and pattern.search(name):
                    results.append(full_path)
                    self.queue.put(("add", full_path))

            if not self.stop_event.is_set():
                cursor.execute("DELETE FROM cache WHERE keyword = ?", (keyword.lower(),))
                for path in results:
                    cursor.execute("INSERT INTO cache (keyword, folder_path) VALUES (?, ?)", (keyword.lower(), path))
                conn.commit()
                self.queue.put(("done", len(results)))
            else:
                self.queue.put(("stopped",))
        except Exception as e:
            self.queue.put(("error", str(e)))
        finally:
            conn.close()

    def process_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg[0] == "add":
                    self.listbox.insert(tk.END, msg[1])
                elif msg[0] == "done":
                    self.status_label.config(text=f"✅ انتهى البحث. {msg[1]} مجلد تم العثور عليهم.")
                    self.search_btn.config(text="🔎 ابحث")
                    self.searching = False
                elif msg[0] == "error":
                    messagebox.showerror("خطأ", msg[1])
                    self.status_label.config(text="❌ حدث خطأ أثناء البحث.")
                    self.search_btn.config(text="🔎 ابحث")
                    self.searching = False
                elif msg[0] == "stopped":
                    self.status_label.config(text="❌ تم إيقاف البحث.")
                    self.search_btn.config(text="🔎 ابحث")
                    self.searching = False
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def open_folder(self, event):
        selected = self.listbox.get(tk.ACTIVE)
        if os.name == 'nt':
            os.startfile(selected)
        else:
            messagebox.showinfo("معلومة", "فتح المجلدات مدعوم فقط على ويندوز.")

    def copy_path(self):
        selected = self.listbox.get(tk.ACTIVE)
        if selected:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
            messagebox.showinfo("تم النسخ", "تم نسخ المسار للحافظة.")
        else:
            messagebox.showwarning("تحذير", "اختر مجلد من القائمة أولاً.")

    def display_results(self, results):
        for path in results:
            self.listbox.insert(tk.END, path)

if __name__ == "__main__":
    root = tk.Tk()
    app = SearchApp(root)
    root.mainloop()