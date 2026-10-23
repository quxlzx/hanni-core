# Per-capability scorecard

Counts come from the freshly enumerated registry; no expected total is assumed. The raw original-handler receipts are preserved locally under `data/campaign2-manager/final-cycle2`. They are hash-bound here rather than copied into documentation with unrelated live host data.

P = passed within the stated fixture scope; F = failed; B = blocked; NA = no optional dependency. Missing-parameter checks document optional/default behavior where the original schema does not require a parameter. NL reports retrieval and host-policy behavior. Model selection is an additional, separate column.

| Capability | Valid | Invalid | Missing | Gates | Absent dep. | Contract | NL | E2E | Valid/E2E scope | Model |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `app.list_installed` | P | P | P | P | P | P | P | P | live read | B |
| `app.open` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `archive.list` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `archive.unzip` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `archive.zip` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `audio.mute` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `audio.set_volume` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `audio.status` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `browser.open_url` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `calc.evaluate` | P | P | P | P | NA | P | P | P | live read | B |
| `clipboard.read` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `clipboard.write` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `device.audio` | P | P | P | P | P | P | P | P | live read | B |
| `device.bluetooth` | P | P | P | P | P | P | P | P | live read | B |
| `device.disk_health` | P | P | P | P | P | P | P | P | live read | B |
| `device.printers` | P | P | P | P | P | P | P | P | live read | B |
| `device.usb` | P | P | P | P | P | P | P | P | live read | B |
| `disk.cleanup_temp` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `disk.folder_size` | P | P | P | P | P | P | F | P | isolated implementation | B |
| `disk.free_space` | P | P | P | P | P | P | P | P | live read | B |
| `disk.largest_files` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `disk.largest_folders` | P | P | P | P | P | P | F | P | isolated implementation | B |
| `disk.recycle_bin_size` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `disk.usage` | P | P | P | P | P | P | P | P | live read | B |
| `display.brightness` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `display.info` | P | P | P | P | P | P | P | P | live read | B |
| `email.read` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `email.search` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `env.get` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `env.list` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `env.path` | P | P | P | P | P | P | P | P | live read | B |
| `env.user_folders` | P | P | P | P | P | P | P | P | live read | B |
| `env.which` | P | P | P | P | P | P | P | P | live read | B |
| `file.compare` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.composition` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.copy` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.delete` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.duplicates` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.empty_folders` | P | P | P | P | P | P | F | P | isolated implementation | B |
| `file.grep` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.head` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.list_dir` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.locate` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.mkdir` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.move` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.open` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `file.read` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.recent` | P | P | P | P | P | P | F | P | isolated implementation | B |
| `file.search` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.stat` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.tail` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `file.write` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `folder.open` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `git.branches` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `git.diff` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `git.log` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `git.status` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `gmail.read` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `gmail.search` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.accounts` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.calendar.availability` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.calendar.create` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.calendar.delete` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.calendar.events` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.calendar.list_calendars` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.calendar.next` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.calendar.read` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.calendar.update` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.docs.read` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.drive.list` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.drive.metadata` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.drive.recent` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.drive.search` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.gmail.read` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.gmail.recent` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `google.gmail.search` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.gmail.thread` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.tasks.complete` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.tasks.create` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google.tasks.list` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google_calendar.agenda` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google_calendar.create` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google_calendar.list` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `google_calendar.next` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `gpu.memory` | P | P | P | P | P | P | P | P | live read | B |
| `gpu.top_processes` | P | P | P | P | P | P | P | P | live read | B |
| `hanni.audit_tail` | P | P | P | P | P | P | P | P | live read | B |
| `hanni.capabilities` | P | P | P | P | NA | P | P | P | live read | B |
| `hanni.permissions` | P | P | P | P | NA | P | P | P | live read | B |
| `hanni.stop_state` | P | P | P | P | NA | P | F | P | live read | B |
| `id.generate` | P | P | P | P | NA | P | P | P | live read | B |
| `media.next_track` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `media.play_pause` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `media.previous_track` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `media.stop` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `model.status` | P | P | P | P | P | P | P | P | live read | B |
| `net.dns_lookup` | P | P | P | P | P | P | P | P | live read | B |
| `net.info` | P | P | P | P | P | P | P | P | live read | B |
| `net.ping` | P | P | P | P | P | P | P | P | live read | B |
| `net.ports` | P | P | P | P | P | P | P | P | live read | B |
| `net.throughput` | P | P | P | P | P | P | P | P | live read | B |
| `net.wifi` | P | P | P | P | P | P | P | P | live read | B |
| `note.append` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `note.days` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `note.list` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `note.search` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `notify.toast` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `power.battery_detail` | P | P | P | P | P | P | P | P | live read | B |
| `power.battery_report` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `power.idle_settings` | P | P | P | P | P | P | P | P | live read | B |
| `power.plans` | P | P | P | P | P | P | P | P | live read | B |
| `power.set_idle` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `power.set_plan` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `powershell.run` | P | P | P | P | P | P | P | P | live read | B |
| `process.find` | P | P | P | P | P | P | F | P | live read | B |
| `process.inspect` | P | P | P | P | P | P | P | P | live read | B |
| `process.list` | P | P | P | P | P | P | F | P | live read | B |
| `process.stop` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `process.top_cpu` | P | P | P | P | P | P | P | P | live read | B |
| `process.top_disk_io` | P | P | P | P | P | P | F | P | live read | B |
| `process.top_memory` | P | P | P | P | P | P | P | P | live read | B |
| `process.uptime` | P | P | P | P | P | P | P | P | live read | B |
| `project.format` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `project.lint` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `project.test` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `python.env_info` | P | P | P | P | P | P | P | P | live read | B |
| `random.number` | P | P | P | P | NA | P | P | P | live read | B |
| `random.pick` | P | P | P | P | NA | P | F | P | live read | B |
| `schedule.list_tasks` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `security.bitlocker` | P | P | P | P | P | P | P | P | live read | B |
| `security.defender` | P | P | P | P | P | P | P | P | live read | B |
| `security.firewall` | P | P | P | P | P | P | P | P | live read | B |
| `security.pending_reboot` | P | P | P | P | P | P | P | P | live read | B |
| `security.updates` | P | P | P | P | P | P | P | P | live read | B |
| `service.control` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `service.list` | P | P | P | P | P | P | P | P | live read | B |
| `spotify.focus` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.launch` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.next` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.open_uri` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.play_pause` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `spotify.previous` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.search` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.status` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `spotify.volume` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `startup.list` | P | P | P | P | P | P | P | P | live read | B |
| `system.battery` | P | P | P | P | P | P | P | P | live read | B |
| `system.event_errors` | P | P | P | P | P | P | P | P | live read | B |
| `system.os_info` | P | P | P | P | P | P | P | P | live read | B |
| `system.performance` | P | P | P | P | P | P | P | P | live read | B |
| `system.stats` | P | P | P | P | P | P | F | P | live read | B |
| `system.uptime` | P | P | P | P | P | P | P | P | live read | B |
| `text.hash` | P | P | P | P | NA | P | P | P | live read | B |
| `text.normalize` | P | P | P | P | NA | P | P | P | live read | B |
| `text.stats` | P | P | P | P | NA | P | P | P | live read | B |
| `time.convert` | P | P | P | P | NA | P | P | P | live read | B |
| `time.elapsed` | P | P | P | P | NA | P | P | P | live read | B |
| `time.now` | P | P | P | P | NA | P | P | P | live read | B |
| `timer.set` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `todo.add` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `todo.complete` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `todo.due` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `todo.get` | P | P | P | P | P | P | F | P | isolated implementation | B |
| `todo.list` | P | P | P | P | P | P | P | P | isolated implementation | B |
| `ui.active_window` | P | P | P | P | P | P | F | P | mock leaf dependency | B |
| `ui.close_window` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `ui.focus_window` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `ui.list_windows` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `ui.minimize_all` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `ui.window_state` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `ui.windows_detailed` | P | P | P | P | P | P | P | P | mock leaf dependency | B |
| `unit.convert` | P | P | P | P | NA | P | P | P | live read | B |
