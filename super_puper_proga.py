#!/usr/bin/env python3
"""
TS Downloader + Video Logo Replacer
Скачивает сегменты, объединяет в MP4 и заменяет логотип
"""
import requests
import time
import subprocess
import os
import glob
import shutil
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import re

# Глобальная сессия для ускорения загрузки
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0',
    'Accept': '*/*',
    'Referer': 'https://anitype.fun/',
    'Origin': 'https://anitype.fun'
})

class VideoDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TS Downloader + Logo Replacer")
        self.root.geometry("800x650")
      
        self.video_files = [] # Список файлов для обработки
        self.video_logo_types = {} # Словарь: файл -> тип логотипа
        self.downloaded_files = []
        self.logo_type = tk.StringVar(value="1") # Тип по умолчанию для новых файлов
        self.default_logo_for_all = tk.StringVar(value="1") # Тип по умолчанию для всех серий
        self.auto_process_after_download = tk.BooleanVar(value=True)  # НОВАЯ ГАЛОЧКА
        self.urls_file = "urls.txt"
      
        self.setup_ui()
        self.load_urls_from_file()

    def setup_ui(self):
        # Заголовок
        title_label = ttk.Label(self.root, text="TS Downloader + Logo Replacer", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # Фрейм для управления URL
        url_frame = ttk.LabelFrame(self.root, text="Управление URL", padding=10)
        url_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(url_frame, text="Загрузить URLs из файла", command=self.load_urls_from_file).pack(side="left", padx=5)
        ttk.Button(url_frame, text="Редактировать URLs", command=self.edit_urls_file).pack(side="left", padx=5)
        ttk.Button(url_frame, text="Скачать все серии", command=self.start_download_all).pack(side="left", padx=5)

        # НОВАЯ ГАЛОЧКА
        ttk.Checkbutton(url_frame, text="Запустить обработку логотипов сразу после скачивания",
                        variable=self.auto_process_after_download).pack(side="left", padx=10)

        # Фрейм для выбора видео
        video_frame = ttk.LabelFrame(self.root, text="Видео файлы для обработки", padding=10)
        video_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Кнопки для выбора видео
        button_frame = ttk.Frame(video_frame)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="Добавить видео", command=self.add_videos).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Очистить список", command=self.clear_list).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Удалить выбранное", command=self.remove_selected).pack(side="left", padx=5)

        # Фрейм со списком видео и выбором логотипа
        list_frame = ttk.Frame(video_frame)
        list_frame.pack(fill="both", expand=True, pady=5)

        # Список выбранных видео с прокруткой
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(side="left", fill="both", expand=True)

        # Заголовки колонок
        header_frame = ttk.Frame(listbox_frame)
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="№", font=("Arial", 9, "bold"), width=3).pack(side="left", padx=2, pady=2)
        ttk.Label(header_frame, text="Видео файл", font=("Arial", 9, "bold")).pack(side="left", padx=5, pady=2)
        ttk.Label(header_frame, text="Тип логотипа", font=("Arial", 9, "bold")).pack(side="right", padx=50, pady=2)

        # Canvas и скроллбар для списка
        canvas = tk.Canvas(listbox_frame)
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Фрейм для выбора логотипа по умолчанию
        logo_frame = ttk.LabelFrame(self.root, text="Настройки логотипа", padding=10)
        logo_frame.pack(fill="x", padx=10, pady=5)

        # Тип логотипа по умолчанию для ВСЕХ серий
        default_all_frame = ttk.Frame(logo_frame)
        default_all_frame.pack(fill="x", pady=5)
        ttk.Label(default_all_frame, text="Тип логотипа для ВСЕХ серий:", font=("Arial", 9, "bold")).pack(side="left", padx=5)
      
        ttk.Radiobutton(default_all_frame, text="Белое лого для всех",
                       variable=self.default_logo_for_all, value="1",
                       command=self.apply_default_logo_to_all).pack(side="left", padx=10)
        ttk.Radiobutton(default_all_frame, text="Красное лого для всех",
                       variable=self.default_logo_for_all, value="2",
                       command=self.apply_default_logo_to_all).pack(side="left", padx=10)

        # Тип логотипа по умолчанию для новых файлов
        default_new_frame = ttk.Frame(logo_frame)
        default_new_frame.pack(fill="x", pady=5)
        ttk.Label(default_new_frame, text="Тип логотипа по умолчанию для новых файлов:").pack(side="left", padx=5)
      
        ttk.Radiobutton(default_new_frame, text="Белое лого",
                       variable=self.logo_type, value="1").pack(side="left", padx=10)
        ttk.Radiobutton(default_new_frame, text="Красное лого",
                       variable=self.logo_type, value="2").pack(side="left", padx=10)

        # Кнопки управления типами логотипов
        button_logo_frame = ttk.Frame(logo_frame)
        button_logo_frame.pack(fill="x", pady=5)
        ttk.Button(button_logo_frame, text="Применить выбранный тип ко всем",
                  command=self.apply_current_logo_to_all).pack(side="left", padx=5)
        ttk.Button(button_logo_frame, text="Сбросить к настройкам по умолчанию",
                  command=self.reset_to_default_logo).pack(side="left", padx=5)

        # Информация о логотипе
        info_label = ttk.Label(logo_frame, text="Используется файл logo3.png (H.265, прозрачность сохранена)",
                              font=("Arial", 8), foreground="green")
        info_label.pack(anchor="w", pady=5)

        # Фрейм для управления
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=10)

        # Прогресс бар
        self.progress = ttk.Progressbar(control_frame, mode='determinate')
        self.progress.pack(fill="x", pady=5)

        # Статус
        self.status_label = ttk.Label(control_frame, text="Готов к работе")
        self.status_label.pack(fill="x", pady=2)

        # Кнопки запуска
        button_frame2 = ttk.Frame(control_frame)
        button_frame2.pack(fill="x", pady=10)
        ttk.Button(button_frame2, text="Начать обработку логотипов", command=self.start_processing).pack(side="left", padx=5)
        ttk.Button(button_frame2, text="Только скачать серии", command=self.start_download_only).pack(side="left", padx=5)

    def add_videos(self):
        files = filedialog.askopenfilenames(
            title="Выберите видео файлы",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.ts"), ("All files", "*.*")]
        )
        if files:
            for file in files:
                if file not in self.video_files:
                    self.video_files.append(file)
                    self.video_logo_types[file] = self.logo_type.get()
            self.update_video_list()

    def remove_selected(self):
        if self.video_files:
            self.video_files.clear()
            self.video_logo_types.clear()
            self.update_video_list()

    def clear_list(self):
        self.video_files.clear()
        self.video_logo_types.clear()
        self.update_video_list()

    def update_video_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        for i, file in enumerate(self.video_files, 1):
            file_frame = ttk.Frame(self.scrollable_frame)
            file_frame.pack(fill="x", pady=2)
            number_label = ttk.Label(file_frame, text=f"{i:02d}", width=3, font=("Arial", 9))
            number_label.pack(side="left", padx=2)
            filename = os.path.basename(file)
            filename_label = ttk.Label(file_frame, text=filename, width=40)
            filename_label.pack(side="left", padx=5)
            logo_var = tk.StringVar(value=self.video_logo_types[file])
          
            logo_frame = ttk.Frame(file_frame)
            logo_frame.pack(side="right", padx=5)
            ttk.Radiobutton(logo_frame, text="Белое", variable=logo_var,
                           value="1", command=lambda f=file, v=logo_var: self.update_file_logo_type(f, v.get())
                          ).pack(side="left", padx=2)
          
            ttk.Radiobutton(logo_frame, text="Красное", variable=logo_var,
                           value="2", command=lambda f=file, v=logo_var: self.update_file_logo_type(f, v.get())
                          ).pack(side="left", padx=2)

    def update_file_logo_type(self, file, logo_type):
        self.video_logo_types[file] = logo_type
        logo_name = "белое" if logo_type == "1" else "красное"
        print(f"Для файла {os.path.basename(file)} установлен тип логотипа: {logo_name}")

    def apply_default_logo_to_all(self):
        new_logo_type = self.default_logo_for_all.get()
        for file in self.video_files:
            self.video_logo_types[file] = new_logo_type
        self.update_video_list()
        logo_name = "белое" if new_logo_type == "1" else "красное"
        messagebox.showinfo("Успех", f"Для всех {len(self.video_files)} серий установлено {logo_name} лого")

    def apply_current_logo_to_all(self):
        new_logo_type = self.logo_type.get()
        for file in self.video_files:
            self.video_logo_types[file] = new_logo_type
        self.update_video_list()
        logo_name = "белое" if new_logo_type == "1" else "красное"
        messagebox.showinfo("Успех", f"Тип логотипа '{logo_name}' применен ко всем {len(self.video_files)} видеофайлам")

    def reset_to_default_logo(self):
        new_logo_type = self.default_logo_for_all.get()
        for file in self.video_files:
            self.video_logo_types[file] = new_logo_type
        self.logo_type.set(new_logo_type)
        self.update_video_list()
        logo_name = "белое" if new_logo_type == "1" else "красное"
        messagebox.showinfo("Успех", f"Все настройки сброшены: для всех серий установлено {logo_name} лого")

    def load_urls_from_file(self):
        if os.path.exists(self.urls_file):
            try:
                with open(self.urls_file, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                self.urls = urls
                messagebox.showinfo("Успех", f"Загружено {len(urls)} URL из файла")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить URLs: {e}")
        else:
            self.urls = []
            messagebox.showinfo("Информация", f"Файл {self.urls_file} не найден")

    def edit_urls_file(self):
        try:
            if not os.path.exists(self.urls_file):
                with open(self.urls_file, 'w', encoding='utf-8') as f:
                    f.write("# Добавьте URLs по одному на строку\n")
          
            if os.name == 'nt':
                os.system(f'notepad "{self.urls_file}"')
            else:
                os.system(f'xdg-open "{self.urls_file}"')
          
            self.load_urls_from_file()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}")

    def start_download_all(self):
        if not self.urls:
            messagebox.showwarning("Предупреждение", "Нет URLs для скачивания!")
            return
        thread = threading.Thread(target=self.download_all_series)
        thread.daemon = True
        thread.start()

    def start_download_only(self):
        if not self.urls:
            messagebox.showwarning("Предупреждение", "Нет URLs для скачивания!")
            return
        thread = threading.Thread(target=self.download_all_series_without_processing)
        thread.daemon = True
        thread.start()

    def start_processing(self):
        if not self.video_files:
            messagebox.showwarning("Предупреждение", "Выберите хотя бы одно видео!")
            return
        if not os.path.exists("logo3.png"):
            messagebox.showerror("Ошибка", "Файл логотипа 'logo3.png' не найден!")
            return
        thread = threading.Thread(target=self.process_videos)
        thread.daemon = True
 hey       thread.start()

    def normalize_url(self, url):
        match = re.search(r'(m3u8)(\d+)(\.ts)', url)
        if match:
            normalized_url = url.replace(match.group(0), "m3u80.ts")
            print(f"Нормализован URL: {url} -> {normalized_url}")
            return normalized_url
        return url

    def download_series(self, url, series_index, total_series):
        """Скачивает, объединяет, конвертирует и очищает ОДНУ серию полностью"""
        normalized_url = self.normalize_url(url)
        url_template = normalized_url.replace("m3u80.ts", "m3u8{}.ts")
      
        episode_num = series_index + 1
        output_name = f"episode_{episode_num:03d}.mp4"
      
        self.root.after(0, self.update_progress, series_index, total_series,
                       f"Скачивается серия {episode_num}...")
        print(f"\nНачало загрузки серии {episode_num}")
        segments_dir = self.ensure_segments_dir(unique=True)
        downloaded_segments = 0
        counter = 0
        max_consecutive_errors = 3
        consecutive_errors = 0
        max_segments = 2000
        while consecutive_errors < max_consecutive_errors and counter < max_segments:
            segment_url = url_template.format(counter)
            success, error_type = self.download_segment_with_retry(
                segment_url, counter, episode_num, segments_dir
            )
          
            if success:
                downloaded_segments += 1
                consecutive_errors = 0
            else:
                if error_type == "not_found":
                    consecutive_errors += 1
                elif error_type == "500_five_times":
                    print(f"Сегмент {counter} — 5 раз 500 ошибка. Завершаем серию.")
                    break
                else:
                    if consecutive_errors > 0:
                        consecutive_errors += 1
            counter += 1
        print(f"Сканирование завершено. Скачано сегментов: {downloaded_segments}")

        if downloaded_segments > 0:
            temp_input = f"temp_combined_{episode_num}.ts"
            if self.combine_segments(segments_dir, episode_num, temp_input):
                if self.convert_to_mp4(temp_input, output_name):
                    self.cleanup_temp_files(segments_dir, temp_input)
                    self.downloaded_files.append(output_name)
                    print(f"Серия {episode_num} успешно сохранена: {output_name}")
                    return True
                else:
                    print("Ошибка конвертации. Сегменты сохранены.")
            else:
                print("Ошибка объединения сегментов")
        else:
            print("Не скачано ни одного сегмента — серия пропущена.")
            self.cleanup_temp_files(segments_dir, None)
        return False

    def ensure_segments_dir(self, unique=True):
        if unique:
            folder_name = f"ts_segments_{uuid.uuid4().hex[:8]}"
        else:
            folder_name = "ts_segments"
        os.makedirs(folder_name, exist_ok=True)
        return folder_name

    def download_segment_with_retry(self, url, segment_num, episode_num, segments_dir, max_retries=5):
        five_hundred_count = 0
        for attempt in range(max_retries):
            try:
                response = session.get(url, timeout=15)
              
                if response.status_code == 200 and len(response.content) > 1000:
                    filename = f"segment_{episode_num}_{segment_num:05d}.ts"
                    filepath = os.path.join(segments_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"Сегмент {segment_num} скачан")
                    return True, "success"
                elif response.status_code == 404:
                    print(f"Сегмент {segment_num} не найден (404)")
                    return False, "not_found"
                elif 500 <= response.status_code < 600:
                    five_hundred_count += 1
                    print(f"Сегмент {segment_num}: 5xx ({response.status_code}), подряд: {five_hundred_count}")
                    if five_hundred_count >= 5:
                        return False, "500_five_times"
                else:
                    print(f"Сегмент {segment_num}: статус {response.status_code}")
            except requests.exceptions.Timeout:
                print(f"Сегмент {segment_num} таймаут")
            except requests.exceptions.ConnectionError:
                print(f"Сегмент {segment_num} ошибка соединения")
            except Exception as e:
                print(f"Сегмент {segment_num} ошибка: {e}")
          
            if attempt < max_retries - 1:
                time.sleep(1)
        return False, "max_retries"

    def combine_segments(self, segments_dir, episode_num, output_file):
        segment_pattern = os.path.join(segments_dir, f"segment_{episode_num}_*.ts")
        segment_files = sorted(glob.glob(segment_pattern), key=lambda x: int(os.path.basename(x).split('_')[-1].split('.')[0]))
        if not segment_files:
            print("Нет сегментов для объединения")
            return False
        try:
            with open(output_file, 'wb') as outfile:
                for segment_file in segment_files:
                    with open(segment_file, 'rb') as infile:
                        outfile.write(infile.read())
            print(f"Объединено {len(segment_files)} сегментов → {output_file}")
            return True
        except Exception as e:
            print(f"Ошибка объединения: {e}")
            return False

    def convert_to_mp4(self, input_file, output_file):
        try:
            print(f"Конвертация {input_file} → {output_file}")
            cmd = ['ffmpeg', '-i', input_file, '-c', 'copy', '-y', output_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Конвертация успешна: {output_file}")
                return True
            else:
                print(f"FFmpeg ошибка: {result.stderr}")
                return False
        except Exception as e:
            print(f"Ошибка конвертации: {e}")
            return False

    def cleanup_temp_files(self, segments_dir, combined_ts_file):
        print("Очистка временных файлов...")
        if combined_ts_file and os.path.exists(combined_ts_file):
            os.remove(combined_ts_file)
        if os.path.exists(segments_dir):
            shutil.rmtree(segments_dir, ignore_errors=True)
        print("Временные файлы удалены")

    def download_all_series(self):
        total_series = len(self.urls)
        self.root.after(0, self.update_ui_processing_start, total_series, "Скачивание серий")
        successful_downloads = 0
      
        for i, url in enumerate(self.urls):
            if self.download_series(url, i, total_series):
                successful_downloads += 1
          
            if i < len(self.urls) - 1:
                print("Пауза 2 сек перед следующей серией...")
                time.sleep(2)

        self.root.after(0, self.update_ui_processing_end, total_series,
                       f"Скачано {successful_downloads} из {total_series} серий")

        if successful_downloads > 0:
            for file in self.downloaded_files:
                if file not in self.video_files:
                    self.video_files.append(file)
                    self.video_logo_types[file] = self.default_logo_for_all.get()
            self.root.after(0, self.update_video_list)

            if self.auto_process_after_download.get():
                messagebox.showinfo("Готово", f"Скачано {successful_downloads} серий. Запуск обработки логотипов...")
                self.root.after(100, self.start_processing)  # Небольшая задержка
            else:
                messagebox.showinfo("Скачивание завершено",
                    f"Скачано {successful_downloads} серий.\n\n"
                    "Расставьте типы логотипов для видео и нажмите кнопку:\n"
                    "«Начать обработку логотипов»")

    def download_all_series_without_processing(self):
        total_series = len(self.urls)
        self.root.after(0, self.update_ui_processing_start, total_series, "Скачивание серий")
        successful_downloads = 0
      
        for i, url in enumerate(self.urls):
            if self.download_series(url, i, total_series):
                successful_downloads += 1
          
            if i < len(self.urls) - 1:
                time.sleep(2)

        self.root.after(0, self.update_ui_processing_end, total_series,
                       f"Скачано {successful_downloads} из {total_series} серий")

        if successful_downloads > 0:
            for file in self.downloaded_files:
                if file not in self.video_files:
                    self.video_files.append(file)
                    self.video_logo_types[file] = self.default_logo_for_all.get()
            self.root.after(0, self.update_video_list)

    def process_videos(self):
        total_videos = len(self.video_files)
        self.root.after(0, self.update_ui_processing_start, total_videos, "Обработка логотипов")
        successful_processing = 0
      
        for i, input_file in enumerate(self.video_files):
            logo_type = self.video_logo_types.get(input_file, "1")
            logo_type_name = "белое" if logo_type == "1" else "красное"
          
            self.root.after(0, self.update_progress, i, total_videos,
                           f"Обрабатывается: {os.path.basename(input_file)} ({logo_type_name} лого)")
            name, ext = os.path.splitext(input_file)
            logo_type_suffix = "white" if logo_type == "1" else "red"
            output_file = f"{name}_logo_{logo_type_suffix}{ext}"
            success = self.process_single_video(input_file, output_file, logo_type)
            if success:
                successful_processing += 1
            else:
                self.root.after(0, messagebox.showerror, "Ошибка",
                               f"Ошибка при обработке файла: {os.path.basename(input_file)}")

        self.root.after(0, self.update_ui_processing_end, total_videos,
                       f"Обработано {successful_processing} из {total_videos} видео")

    def process_single_video(self, input_file, output_file, logo_type):
        try:
            logo_type_name = "белое" if logo_type == "1" else "красное"
            print(f"Добавляю {logo_type_name} логотип к {os.path.basename(input_file)}...")
            if logo_type == "1":
                cmd = [
                    'ffmpeg', '-i', input_file, '-i', 'logo3.png',
                    '-filter_complex',
                    '[0:v]delogo=x=3517:y=48:w=252:h=105:show=0[cleaned];'
                    '[1:v]scale=400:167[scaled_logo];'
                    '[cleaned][scaled_logo]overlay=3417:28',
                    '-c:v', 'libx265', '-preset', 'medium', '-crf', '20',
                    '-c:a', 'copy', '-movflags', '+faststart', '-y', output_file
                ]
            else:
                cmd = [
                    'ffmpeg', '-i', input_file, '-i', 'logo3.png',
                    '-filter_complex',
                    "[0:v]crop=370:322:3377:0,delogo=x=1:y=1:w=364:h=320:enable='lt(t,2)'[delogo1];"
                    "[0:v]crop=366:90:3377:92,delogo=x=1:y=1:w=364:h=88:enable='gte(t,2)'[delogo2];"
                    "[0:v][delogo1]overlay=3377:0:enable='lt(t,2)'[temp];"
                    "[temp][delogo2]overlay=3377:92:enable='gte(t,2)'[cleaned];"
                    "[1:v]format=rgba,scale=400:167[scaled_logo];"
                    "[cleaned][scaled_logo]overlay=3417:28",
                    '-c:v', 'libx265', '-preset', 'medium', '-crf', '20',
                    '-c:a', 'copy', '-movflags', '+faststart', '-y', output_file
                ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Видео с {logo_type_name} логотипом готово: {output_file}")
                return True
            else:
                print(f"Ошибка добавления логотипа: {result.stderr}")
                return False
        except Exception as e:
            print(f"Ошибка при обработке: {e}")
            return False

    def update_ui_processing_start(self, total, process_type):
        self.progress['maximum'] = total
        self.progress['value'] = 0
        self.status_label.config(text=f"Начата {process_type}...")

    def update_progress(self, current, total, status):
        self.progress['value'] = current + 1
        self.status_label.config(text=status)
        self.root.update_idletasks()

    def update_ui_processing_end(self, total, message):
        self.progress['value'] = total
        self.status_label.config(text=message)


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoDownloaderApp(root)
    root.mainloop()
