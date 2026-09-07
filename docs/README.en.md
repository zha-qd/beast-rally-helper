# Whiteout Survival Beast Rally Helper | 无尽冬日 / 寒霜启示录 巨兽集结助手

A Windows desktop rally assistant with a white UI, up to three-window cycling, OCR march counts, one-soldier mode, time limits and calibration tools. The application UI is in Chinese.

[中文说明](../README.md) · [Downloads](https://github.com/zha-qd/beast-rally-helper/releases)

## Portable quick start

1. Download `beast-rally-helper-v1.0.0-windows-x64.zip` and fully extract it into a writable folder.
2. Run `start.bat`. Python, dependencies and Chinese OCR models are bundled.
3. Open the game's world map, enter a unique window title and enable that slot. Titles start empty.
4. Click Detect, then check calibration and test march OCR before starting.
5. Set levels and optional time limit / one-soldier mode. Save configuration.
6. Press F5 to start/stop, F6 to pause/resume, or F8 to stop. F8 does not exit.

GitHub's automatic source archives and the source ZIP do not include the runtime. Use the Windows ZIP for the ready-to-run package.

## Environment and controls

Windows x64; portable runtime: Python 3.10, PaddleOCR 2.7.0.3 and PaddlePaddle 2.6.2. This captures the visible desktop and controls the mouse; it does not work with minimized or covered game windows. Keep layout, position and scaling stable. Multi-window cycling attempts to activate the selected window and uses one shared coordinate profile.

| UI label | Meaning |
| --- | --- |
| 窗口 1–3 | Target window title and enable switch |
| 检测 | Find and attempt to activate that window; first matching title wins |
| 巡检间隔 | Polling / full-cycle wait, default 10 seconds |
| 点击延迟 | Default click delay, 0.8 seconds |
| 搜索等待 / 集结等待 | Search / rally delay, 1.5 / 1.0 seconds |
| 巨兽等级 | Minimum/maximum target level, supported range 1–8 |
| 一兵集结 | Recall all selected troops, add one soldier, then march |
| 限时运行 | Stop after the selected hours; off by default |
| 调试截图 | Save recognition screenshots to debug_img |
| 保存当前配置 | Save parameters and calibration |

Short-press hotkeys; avoid holding them or running competing automation. The existing stop/pause behavior may finish a wait before reacting. Moving the pointer to a screen corner can trigger the PyAutoGUI fail-safe. Stop before closing the application.

## Rally workflow

- Read current/max march count. If full, wait or advance to the next enabled window.
- Open search, select beasts, set level, search, rally and start rally.
- Read travel time. If over 60 seconds, decrease the target level for the **next** search, wrapping to the selected maximum after the minimum. The current rally is not cancelled.
- If the stamina number is red, attempt the stamina refill flow before marching.
- One-soldier mode recalls the selected troops and adds one soldier before march.
- Check march OCR again; if still unreadable twice, click Back twice to recover.
- Cycle through enabled titled slots, waiting between full cycles.

The original automation rules are preserved. On the first round, missing march OCR may be treated as having no marches, so a search is attempted. Later failures use a secondary march-region check and recovery clicks; three consecutive failures also trigger Back. Confirm the starting screen and calibration before use.

Counters reflect executed workflows, not a server-confirmed tally of successful rallies. Recognition and clicks can be affected by lag.

## Calibration

Stop first. Detect the intended game window, choose a click point, press the countdown capture button and move the pointer onto the target within approximately 3 seconds. The relative coordinates are saved. Preview moves the pointer through the points.

For OCR regions, select march count, stamina, secondary marching, travel time or beast level. Capture the top-left and bottom-right corners separately, then use the matching test button. Avoid unrelated numbers in the region.

Reference dimensions are 777 × 1396 including the title bar. Proportional scaling does not compensate for redesigned UI or different DPI/title-bar layouts. All three slots share the same calibration.

## Files and troubleshooting

- `beast_rally_config.json`: created by Save / Start / calibration; personal saved configuration is not included in the release or tracked by Git.
- `logs/startup.log`: startup diagnostics, overwritten each launch. Use `debug_run.bat` for console output.
- `debug_img/`: recognition screenshots; review them before sharing a report.
- On-screen runtime logs are not automatically archived.

If startup fails, fully extract the package and keep runtime alongside start.bat. If detection fails, enter a unique title and enable that slot. For misplaced clicks or OCR errors, recalibrate and use test buttons. One-soldier mode requires accurate recall/add/march points. Stamina refill requires matching dialog coordinates. Test with a small batch before longer runs.

## Source and tests

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe auto_beast_rally_gui.py
runtime\python.exe tests\test_logic.py
```

The portable environment is the tested distribution. Fresh transitive dependencies may differ; see runtime-packages.json. Do not upgrade directly to PaddleOCR 3.x. Without local models, source runs may download models and require network access.

Validation covers parser/config tests, UI and saved configuration checks, and offline initialization of the copied runtime with bundled Chinese models. Not validated across every emulator, DPI setting, multi-window combination or long-running workload.

See [third-party notices](../THIRD_PARTY_NOTICES.md). No license has been selected for the project's own code; public availability alone does not grant unrestricted redistribution rights.
