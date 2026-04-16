using System.Diagnostics;
using System.Runtime.InteropServices;

namespace AutoClicker.Engine;

public sealed class ClickLoop
{
    private readonly object _configLock = new();
    private EngineConfig _config = new();
    private volatile bool _running;
    private Task? _task;
    private readonly CancellationTokenSource _shutdown = new();
    private readonly Action<object> _emitMessage;
    private bool _highPrecisionActive;
    private uint? _previousPriorityClass;

    public ClickLoop(Action<object> emitMessage)
    {
        _emitMessage = emitMessage;
    }

    public void UpdateConfig(EngineConfig config)
    {
        lock (_configLock)
        {
            _config = config;
        }
    }

    public void Start()
    {
        if (_running)
        {
            return;
        }

        _running = true;
        _task = Task.Run(RunLoopAsync);
    }

    public void Stop()
    {
        _running = false;
    }

    public async Task ShutdownAsync()
    {
        _running = false;
        _shutdown.Cancel();
        DisableHighPrecisionTimer();
        DisablePriorityBoost();
        if (_task is not null)
        {
            await _task.ConfigureAwait(false);
        }
    }

    private async Task RunLoopAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        double nextTick = stopwatch.Elapsed.TotalMilliseconds;
        double? lastClickTick = null;

        while (!_shutdown.IsCancellationRequested)
        {
            if (!_running)
            {
                DisableHighPrecisionTimer();
                DisablePriorityBoost();
                await Task.Delay(20, _shutdown.Token).ConfigureAwait(false);
                nextTick = stopwatch.Elapsed.TotalMilliseconds;
                lastClickTick = null;
                continue;
            }

            EngineConfig current;
            lock (_configLock)
            {
                current = _config;
            }

            ApplyRuntimeTuning(current);
            var intervalMs = Math.Max(1.0, current.IntervalMs);
            var offsetLow = Math.Max(0, Math.Min(current.RandomIntervalOffsetMinMs, current.RandomIntervalOffsetMaxMs));
            var offsetHigh = Math.Max(0, Math.Max(current.RandomIntervalOffsetMinMs, current.RandomIntervalOffsetMaxMs));
            if (offsetHigh > 0)
            {
                intervalMs += Random.Shared.Next(offsetLow, offsetHigh + 1);
            }

            nextTick += intervalMs;

            while (stopwatch.Elapsed.TotalMilliseconds < nextTick && !_shutdown.IsCancellationRequested && _running)
            {
                await Task.Delay(1, _shutdown.Token).ConfigureAwait(false);
            }

            if (!_running || _shutdown.IsCancellationRequested)
            {
                continue;
            }

            PerformClick(current);
            var clickTick = stopwatch.Elapsed.TotalMilliseconds;
            if (lastClickTick.HasValue)
            {
                var actualIntervalMs = clickTick - lastClickTick.Value;
                var targetIntervalMs = intervalMs;
                _emitMessage(new
                {
                    type = "syncSample",
                    actualIntervalMs,
                    targetIntervalMs,
                    late = actualIntervalMs - targetIntervalMs > 2
                });
            }
            lastClickTick = clickTick;
        }
    }

    private static void PerformClick(EngineConfig config)
    {
        NativeMethods.GetCursorPos(out var originalPoint);
        var moved = false;
        if (config.JitterEnabled && config.JitterRadiusPx > 0)
        {
            var dx = Random.Shared.Next(-config.JitterRadiusPx, config.JitterRadiusPx + 1);
            var dy = Random.Shared.Next(-config.JitterRadiusPx, config.JitterRadiusPx + 1);
            if (dx != 0 || dy != 0)
            {
                NativeMethods.SetCursorPos(originalPoint.X + dx, originalPoint.Y + dy);
                moved = true;
            }
        }

        var clickCount = config.DoubleClick ? 2 : 1;
        for (var i = 0; i < clickCount; i++)
        {
            SendMouseClick(config.Button);
        }

        if (moved)
        {
            NativeMethods.SetCursorPos(originalPoint.X, originalPoint.Y);
        }
    }

    private static void SendMouseClick(string button)
    {
        var (downFlag, upFlag) = button.Trim().ToLowerInvariant() switch
        {
            "right" => (NativeMethods.MOUSEEVENTF_RIGHTDOWN, NativeMethods.MOUSEEVENTF_RIGHTUP),
            "middle" => (NativeMethods.MOUSEEVENTF_MIDDLEDOWN, NativeMethods.MOUSEEVENTF_MIDDLEUP),
            _ => (NativeMethods.MOUSEEVENTF_LEFTDOWN, NativeMethods.MOUSEEVENTF_LEFTUP),
        };

        var inputs = new[]
        {
            new NativeMethods.INPUT
            {
                type = NativeMethods.INPUT_MOUSE,
                U = new NativeMethods.InputUnion
                {
                    mi = new NativeMethods.MOUSEINPUT { dwFlags = downFlag }
                }
            },
            new NativeMethods.INPUT
            {
                type = NativeMethods.INPUT_MOUSE,
                U = new NativeMethods.InputUnion
                {
                    mi = new NativeMethods.MOUSEINPUT { dwFlags = upFlag }
                }
            }
        };

        NativeMethods.SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<NativeMethods.INPUT>());
    }

    private void ApplyRuntimeTuning(EngineConfig config)
    {
        if (config.HighPrecisionTiming)
        {
            EnableHighPrecisionTimer();
        }
        else
        {
            DisableHighPrecisionTimer();
        }

        if (config.ProcessPriorityBoost)
        {
            EnablePriorityBoost();
        }
        else
        {
            DisablePriorityBoost();
        }
    }

    private void EnableHighPrecisionTimer()
    {
        if (_highPrecisionActive)
        {
            return;
        }

        if (NativeMethods.timeBeginPeriod(1) == 0)
        {
            _highPrecisionActive = true;
        }
    }

    private void DisableHighPrecisionTimer()
    {
        if (!_highPrecisionActive)
        {
            return;
        }

        NativeMethods.timeEndPeriod(1);
        _highPrecisionActive = false;
    }

    private void EnablePriorityBoost()
    {
        if (_previousPriorityClass.HasValue)
        {
            return;
        }

        var process = NativeMethods.GetCurrentProcess();
        var currentPriority = NativeMethods.GetPriorityClass(process);
        _previousPriorityClass = currentPriority == 0 ? null : currentPriority;
        if (NativeMethods.SetPriorityClass(process, NativeMethods.HIGH_PRIORITY_CLASS))
        {
            return;
        }

        _previousPriorityClass = null;
    }

    private void DisablePriorityBoost()
    {
        if (!_previousPriorityClass.HasValue)
        {
            return;
        }

        var process = NativeMethods.GetCurrentProcess();
        NativeMethods.SetPriorityClass(process, _previousPriorityClass.Value);
        _previousPriorityClass = null;
    }
}
