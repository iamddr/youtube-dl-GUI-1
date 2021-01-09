import math
import os

import youtube_dl
from PyQt5 import QtCore


class StopError(Exception):
    pass


class DownloadSignals(QtCore.QObject):
    "Define the signals available from a running download thread"
    
    status_bar_signal = QtCore.pyqtSignal(str)
    remove_url_signal = QtCore.pyqtSignal(str)
    add_update_list_signal = QtCore.pyqtSignal([list])
    remove_row_signal = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()


class Download(QtCore.QRunnable):
    "Download Thread"

    def __init__(self, opts):
        super(Download, self).__init__()
        self.parent = opts.get('parent')
        self.error_occurred = False
        self.done = False
        self.file_name = ""
        self.speed = '-- KiB/s'
        self.eta = "00:00"
        self.bytes = self.format_bytes(None)
        self.url = opts.get('url')
        self.directory = opts.get('directory')
        if self.directory != '':
            self.directory = os.path.join(opts.get('directory'), '')
        self.local_rowcount = opts.get('rowcount')
        self.convert_format = opts.get('convert_format')
        self.proxy = opts.get('proxy')
        self.keep_file = opts.get('keep_file')
        # Signals
        self.signals = DownloadSignals()

    def hook(self, li):
        if self.done:
            raise StopError()

        if li.get('downloaded_bytes') is not None:
            if li.get('speed') is not None:
                self.speed = self.format_speed(li.get('speed'))
                self.eta = self.format_seconds(li.get('eta'))
                self.bytes = 'unknown'
                if li.get('total_bytes') is not None:
                    self.bytes = self.format_bytes(li.get('total_bytes'))
                filename = os.path.split(li.get('filename'))[-1].split('.')[0]
                self.signals.add_update_list_signal.emit([
                    self.local_rowcount,
                    filename,
                    self.bytes,
                    self.eta,
                    self.speed,
                    li.get('status')
                ])

            elif li.get('status') == "finished":
                self.file_name = os.path.split(li.get('filename'))[-1].split('.')[0]
                self.signals.add_update_list_signal.emit([
                    self.local_rowcount,
                    self.file_name,
                    self.bytes,
                    self.eta,
                    self.speed,
                    'Converting'
                ])
        else:
            self.bytes = self.format_bytes(li.get('total_bytes'))
            self.file_name = li.get('filename').split('/')[-1]
            self.speed = '-- KiB/s'

            self.signals.add_update_list_signal.emit([
                self.local_rowcount,
                self.file_name,
                self.bytes,
                '00:00',
                self.speed,
                'Finished'
            ])
            self.signals.status_bar_signal.emit('Already Downloaded')
            self.signals.remove_row_signal.emit()

    def _prepare_ytd_options(self):
        ydl_options = {
            'outtmpl': '{0}%(title)s-%(id)s.%(ext)s'.format(self.directory),
            'continuedl': True,
            'quiet': True,
            'proxy': self.proxy,
        }
        if self.convert_format is not False:
            ydl_options['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': self.convert_format,
            }]

        if self.keep_file:
            ydl_options['keepvideo'] = True
        return ydl_options

    def download(self):
        ydl_options = self._prepare_ytd_options()
        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            ydl.add_default_info_extractors()
            ydl.add_progress_hook(self.hook)
            try:
                ydl.download([self.url])
            except (
                    youtube_dl.utils.DownloadError,
                    youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError,
                    youtube_dl.utils.UnavailableVideoError
            ) as e:
                self.error_occurred = True
                self.signals.remove_row_signal.emit()
                self.signals.remove_url_signal.emit(self.url)
                self.signals.status_bar_signal.emit(str(e))
            except StopError:
                # import threading
                # print("Exiting thread:", threading.currentThread().getName())
                self.done = True
                self.signals.finished.emit()  # Done

    @QtCore.pyqtSlot()
    def run(self):
        self.signals.add_update_list_signal.emit([
            self.local_rowcount,
            self.url,
            '',
            '',
            '',
            'Starting'
        ])

        self.download()
        if self.error_occurred is not True:
            self.signals.add_update_list_signal.emit([
                self.local_rowcount,
                self.file_name,
                self.bytes,
                '00:00',
                self.speed,
                'Finished'
            ])

            self.signals.status_bar_signal.emit('Done!')
        self.signals.remove_url_signal.emit(self.url)
        self.done = True
        self.signals.finished.emit()  # Done
    
    def stop(self):
        self.done = True

    def format_seconds(self, seconds):
        (minutes, secs) = divmod(seconds, 60)
        (hours, minutes) = divmod(minutes, 60)
        if hours > 99:
            return '--:--:--'
        if hours == 0:
            return '%02d:%02d' % (minutes, secs)
        else:
            return '%02d:%02d:%02d' % (hours, minutes, secs)

    def format_bytes(self, bytes):
        if bytes is None:
            return 'N/A'
        if type(bytes) is str:
            bytes = float(bytes)
        if bytes == 0.0:
            exponent = 0
        else:
            exponent = int(math.log(bytes, 1024.0))
        suffix = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'][exponent]
        converted = float(bytes) / float(1024 ** exponent)
        return '%.2f%s' % (converted, suffix)

    def format_speed(self, speed):
        if speed is None:
            return '%10s' % '---b/s'
        return '%10s' % ('%s/s' % self.format_bytes(speed))