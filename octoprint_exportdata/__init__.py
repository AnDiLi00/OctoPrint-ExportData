# coding=utf-8
from __future__ import absolute_import

import os

import octoprint.plugin
from octoprint.util import RepeatedTimer


class ExportDataPlugin(octoprint.plugin.SettingsPlugin,
					   octoprint.plugin.StartupPlugin,
					   octoprint.plugin.TemplatePlugin):
	folder = ""

	temperature_file = ""
	temperature_data = None

	status_file = ""
	status_data = None

	timer = None

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			folder="/home/pi/exportdata/",
			temperature_file="temperature.txt",
			status_file="status.txt"
		)

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		self.check_files(self._settings.get(["folder"]),
						 self._settings.get(["temperature_file"]),
						 self._settings.get(["status_file"]))

	##~~ StartupPlugin mixin

	def on_after_startup(self):
		self.check_files(self._settings.get(["folder"]),
						 self._settings.get(["temperature_file"]),
						 self._settings.get(["status_file"]))

	##~~ TemplatePlugin mixin

	def get_template_configs(self):
		return [{"type": "settings", "custom_bindings": False}]

	##~~ Class specific

	def check_files(self, new_folder, new_temperature, new_status):
		self._logger.info("new settings:")
		self._logger.info("-- folder={}".format(new_folder))
		self._logger.info("-- temperature={}".format(new_temperature))
		self._logger.info("-- status={}".format(new_status))

		changed = False

		if self.folder != new_folder:
			self.remove_file(self.folder, self.temperature_file)
			self.remove_file(self.folder, self.status_file)
			self.remove_path(self.folder)

			self.touch_path(new_folder)
			changed = True

		if self.temperature_file != new_temperature:
			self.remove_file(self.folder, self.temperature_file)
			changed = True

		if self.status_file != new_status:
			self.remove_file(self.folder, self.status_file)
			changed = True

		if changed:
			self.folder = new_folder
			self.temperature_file = new_temperature
			self.status_file = new_status

			self.start_timer()

	def start_timer(self):
		self.stop_timer()

		self.timer = RepeatedTimer(2.0, self.update_values, run_first=True)
		self.timer.start()

	def stop_timer(self):
		if self.timer:
			self.timer.cancel()
			self.timer = None

	def update_values(self):
		self.status_data = self._printer.get_current_data()
		self.temperature_data = self._printer.get_current_temperatures()

		self.update_temperature()
		self.update_status()

	def update_temperature(self):
		data = ""

		if self.temperature_data:
			if "tool0" in self.temperature_data:
				data += "nozzle: "
				data += str("{:.1f}".format(self.temperature_data["tool0"]["actual"])).rjust(5)
				data += "°C of "
				data += str("{:.1f}".format(self.temperature_data["tool0"]["target"])).rjust(5)
				data += "°C"

			if data:
				data += "\n"

			if "bed" in self.temperature_data:
				data += "bed:    "
				data += str("{:.1f}".format(self.temperature_data["bed"]["actual"])).rjust(5)
				data += "°C of "
				data += str("{:.1f}".format(self.temperature_data["bed"]["target"])).rjust(5)
				data += "°C"

		self.touch_file(self.folder, self.temperature_file, data)

	def update_status(self):
		data = ""

		if self.status_data:
			printing = False

			if "state" in self.status_data:
				state_dict = self.status_data["state"]
				flags_dict = state_dict["flags"]

				if flags_dict["cancelling"] or \
					flags_dict["finishing"] or \
					flags_dict["paused"] or \
					flags_dict["pausing"] or \
					flags_dict["printing"]:
					printing = True

				data += "state:   "
				data += state_dict["text"].lower()

			if printing:
				data += "\n"

				if "job" in self.status_data:
					job_dict = self.status_data["job"]

					if "file" in job_dict:
						if job_dict["file"]["name"] is None:
							data += "file:    -"
						else:
							data += "file:    "
							data += job_dict["file"]["name"]
					else:
						data += "file:    -"

					data += "\n"

				if "progress" in self.status_data:
					progress_dict = self.status_data["progress"]
					print_time = progress_dict["printTime"]
					print_time_left = progress_dict["printTimeLeft"]

					if print_time:
						data += "elapsed: "
						data += self.seconds_to_text(print_time)
					else:
						data += "elapsed: 0s"

					data += "\n"

					if print_time_left:
						data += "left:    "
						data += self.seconds_to_text(print_time_left)
					else:
						data += "left:    0s"

					data += "\n"

					if print_time and print_time_left:
						float_percent = 100.0 * float(print_time / (print_time_left + print_time))

						data += "percent: "
						data += str("{:.1f}".format(float_percent))
						data += "%"
					else:
						data += "percent: 0.0%"
			else:
				data = "\n\n\n\n" + data

		self.touch_file(self.folder, self.status_file, data)

	def get_update_information(self):
		return dict(
			test=dict(
				displayName="OctoPrint ExportData",
				displayVersion=self._plugin_version,

				type="github_release",
				user="andili00",
				repo="OctoPrint-ExportData",
				current=self._plugin_version,

				pip="https://github.com/andili00/OctoPrint-ExportData/archive/{target_version}.zip"
			)
		)

	def touch_file(self, path, file, data):
		joined = os.path.join(path, file)

		if path:
			if file:
				self.touch_path(path)

				try:
					file_tmp = open(joined, 'w+')
					file_tmp.write(data)
					file_tmp.close()
				except OSError as error:
					self._logger.error("file '{}' couldn't be created - errno:{}".format(joined, error.errno))
			else:
				self._logger.error("file not valid")
		else:
			self._logger.error("path not valid")

	def remove_file(self, path, file):
		joined = os.path.join(path, file)

		if path:
			if file:
				if os.path.exists(joined):
					try:
						os.remove(joined)
					except OSError as error:
						self._logger.error("file '{}' couldn't be removed - errno:{}".format(joined, error.errno))
				else:
					self._logger.error("file does not exist")
			else:
				self._logger.error("file not valid")
		else:
			self._logger.error("path not valid")

	def touch_path(self, path):
		if path:
			if os.path.exists(path):
				pass
			else:
				try:
					os.makedirs(path, exist_ok=True)
				except OSError as error:
					self._logger.error("path '{}' couldn't be created - errno:{}".format(path, error.errno))
		else:
			self._logger.error("path not valid")

	def remove_path(self, path):
		if path:
			if os.path.exists(path):
				try:
					os.rmdir(path)
				except OSError as error:
					self._logger.error("path '{}' couldn't be removed - errno:{}".format(path, error.errno))
			else:
				self._logger.error("path does not exist")
		else:
			self._logger.error("path not valid")

	@staticmethod
	def seconds_to_text(seconds):
		result = ""

		days = seconds // 86400
		hours = (seconds - days * 86400) // 3600
		minutes = (seconds - days * 86400 - hours * 3600) // 60
		seconds = seconds - days * 86400 - hours * 3600 - minutes * 60

		if days > 0:
			result = "{}d{}h{}m{}s".format(days, hours, minutes, seconds)
		elif hours > 0:
			result = "{}h{}m{}s".format(hours, minutes, seconds)
		elif minutes > 0:
			result = "{}m{}s".format(minutes, seconds)
		elif seconds >= 0:
			result = "{}s".format(seconds)

		return result


__plugin_name__ = "ExportData Plugin"
__plugin_author__ = "Andreas Pecuch"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = ExportDataPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
