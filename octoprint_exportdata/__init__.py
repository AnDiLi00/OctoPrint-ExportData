# coding=utf-8
from __future__ import absolute_import

import os
import math
import octoprint.plugin
from octoprint.util import RepeatedTimer


class ExportdataPlugin(octoprint.plugin.SettingsPlugin,
					   octoprint.plugin.StartupPlugin,
					   octoprint.plugin.TemplatePlugin):
	folder = ""
	temp_file = ""
	status_file = ""

	timer = None
	printer_data = None
	temperature_data = None

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			folder="~/export/",
			temperature="temperature.txt",
			printstatus="printstatus.txt"
		)

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		self.check_files(self._settings.get(["folder"]),
						 self._settings.get(["temperature_file"]),
						 self._settings.get(["printstatus_file"]))

	##~~ StartupPlugin mixin

	def on_after_startup(self):
		self.check_files(self._settings.get(["folder"]),
						 self._settings.get(["temperature_file"]),
						 self._settings.get(["printstatus_file"]))

	##~~ TemplatePlugin mixin

	def get_template_configs(self):
		return [{"type": "settings", "custom_bindings": False}]

	##~~ Class specific

	def check_files(self, new_folder, new_temp, new_status):
		directory_changed = False
		temp_changed = False
		status_changed = False

		if self.folder != new_folder:
			try:
				os.makedirs(new_folder, exist_ok=True)
				self._logger.debug("folder changed from {self.folder} to {new_folder}".format(**locals()))
				self.folder = new_folder
				directory_changed = True
			except OSError as error:
				self._logger.debug("directory {new_folder} couldn't be created".format(**locals()))

		if self.temp_file != new_temp:
			self._logger.debug("temperature file changed from {self.temp_file} to {new_temp}".format(**locals()))
			self.temp_file = new_temp
			temp_changed = True

		if self.status_file != new_status:
			self._logger.debug("status file changed from {self.status_file} to {new_status}".format(**locals()))
			self.status_file = new_status
			status_changed = True

		if directory_changed or temp_changed or status_changed:
			self.start_timer()

	def start_timer(self):
		if self.timer:
			self.timer.cancel()
			self.timer = None

		self.timer = RepeatedTimer(5.0, self.update_values, run_first=True)
		self.timer.start()

	def update_values(self):
		self.printer_data = self._printer.get_current_data()
		self.temperature_data = self._printer.get_current_temperatures()

		self.write_temperature()
		self.write_status()

	def write_temperature(self):
		write_data = ""

		if self.temperature_data:
			if "tool0" in self.temperature_data:
				write_data += "nozzle: "
				write_data += str("{:.1f}".format(self.temperature_data["tool0"]["actual"])).rjust(5)
				write_data += "°C of "
				write_data += str("{:.1f}".format(self.temperature_data["tool0"]["target"])).rjust(5)
				write_data += "°C"

			if write_data:
				write_data += "\n"

			if "bed" in self.temperature_data:
				write_data += "bed:    "
				write_data += str("{:.1f}".format(self.temperature_data["bed"]["actual"])).rjust(5)
				write_data += "°C of "
				write_data += str("{:.1f}".format(self.temperature_data["bed"]["target"])).rjust(5)
				write_data += "°C"

		self.touch(self.folder, self.temp_file, write_data)

	def write_status(self):
		write_data = ""

		if self.printer_data:
			flag_paused = False
			flag_printing = False
			flag_pausing = False
			flag_canceling = False
			flag_finishing = False

			if "state" in self.printer_data:
				state_dict = self.printer_data["state"]
				flags_dict = state_dict["flags"]

				flag_paused = flags_dict["paused"]
				flag_printing = flags_dict["printing"]
				flag_pausing = flags_dict["pausing"]
				flag_canceling = flags_dict["cancelling"]
				flag_finishing = flags_dict["finishing"]

				write_data += "state:   "
				write_data += state_dict["text"].lower()

			self._logger.debug("paused:    {flag_paused}".format(**locals()))
			self._logger.debug("printing:  {flag_printing}".format(**locals()))
			self._logger.debug("pausing:   {flag_pausing}".format(**locals()))
			self._logger.debug("canceling: {flag_canceling}".format(**locals()))
			self._logger.debug("finishing: {flag_finishing}".format(**locals()))

			if flag_paused or flag_printing or flag_pausing or flag_canceling or flag_finishing:
				write_data += "\n"

				if "job" in self.printer_data:
					job_dict = self.printer_data["job"]

					if "file" in job_dict:
						if job_dict["file"]["name"] is None:
							write_data += "file:    -"
						else:
							write_data += "file:    "
							write_data += job_dict["file"]["name"]
					else:
						write_data += "file:    -"

					write_data += "\n"

				if "progress" in self.printer_data:
					progress_dict = self.printer_data["progress"]
					print_time = progress_dict["printTime"]
					print_time_left = progress_dict["printTimeLeft"]

					if print_time is None:
						write_data += "elapsed: 0s"
					else:
						write_data += "elapsed: "
						write_data += self.sec_to_text(print_time)

					write_data += "\n"

					if print_time_left is None:
						write_data += "left:    0s"
					else:
						write_data += "left:    "
						write_data += self.sec_to_text(print_time_left)

					write_data += "\n"

					if print_time is None or print_time_left is None:
						write_data += "percent: 0.0%"
					else:
						float_percent = 100.0 * float(print_time / (print_time_left + print_time))

						write_data += "percent: "
						write_data += str("{:.1f}".format(float_percent))
						write_data += "%"
			else:
				write_data = "\n\n\n\n" + write_data

		self.touch(self.folder, self.status_file, write_data)

	def get_update_information(self):
		return dict(
			test=dict(
				displayName="OctoPrint ExportData",
				displayVersion=self._plugin_version,

				type="github_release",
				user="andili00",
				repo="OctoPrint-Exportdata",
				current=self._plugin_version,

				pip="https://github.com/andili00/OctoPrint-Exportdata/archive/{target_version}.zip"
			)
		)

	@staticmethod
	def touch(path, filename, data):
		if filename:
			file_tmp = open(os.path.join(path, filename), 'w+')
			file_tmp.write(data)
			file_tmp.close()

	@staticmethod
	def sec_to_text(seconds):
		result = ""

		days = seconds // 86400
		hours = (seconds - days * 86400) // 3600
		minutes = (seconds - days * 86400 - hours * 3600) // 60
		seconds = seconds - days * 86400 - hours * 3600 - minutes * 60

		if days > 0:
			result = "{}d".format(days) + "{}h".format(hours) + "{}m".format(minutes) + "{}s".format(seconds)
		elif hours > 0:
			result = "{}h".format(hours) + "{}m".format(minutes) + "{}s".format(seconds)
		elif minutes > 0:
			result = "{}m".format(minutes) + "{}s".format(seconds)
		elif seconds >= 0:
			result = "{}s".format(seconds)

		return result


__plugin_name__ = "Export Data Plugin"
__plugin_author__ = "Andreas Pecuch"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = ExportdataPlugin()
