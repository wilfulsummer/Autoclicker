using System.Text.Json;

namespace AutoClicker.Engine;

public sealed class EngineRuntime
{
    private readonly ClickLoop _clickLoop;

    public EngineRuntime()
    {
        _clickLoop = new ClickLoop(payload => Console.WriteLine(JsonProtocol.Serialize(payload)));
    }

    public async Task RunAsync()
    {
        Console.OutputEncoding = System.Text.Encoding.UTF8;
        Console.WriteLine(JsonProtocol.Serialize(new { type = "ready", engineVersion = "0.1.0" }));

        while (true)
        {
            var line = await Console.In.ReadLineAsync().ConfigureAwait(false);
            var doc = JsonProtocol.Parse(line);
            if (doc is null)
            {
                continue;
            }

            using (doc)
            {
                var root = doc.RootElement;
                if (!root.TryGetProperty("type", out var typeElement))
                {
                    continue;
                }

                var type = typeElement.GetString()?.Trim().ToLowerInvariant();
                switch (type)
                {
                    case "configure":
                        _clickLoop.UpdateConfig(ReadConfig(root));
                        Console.WriteLine(JsonProtocol.Serialize(new { type = "state", configured = true }));
                        break;
                    case "start":
                        _clickLoop.Start();
                        Console.WriteLine(JsonProtocol.Serialize(new { type = "state", running = true }));
                        break;
                    case "stop":
                        _clickLoop.Stop();
                        Console.WriteLine(JsonProtocol.Serialize(new { type = "state", running = false }));
                        break;
                    case "shutdown":
                        await _clickLoop.ShutdownAsync().ConfigureAwait(false);
                        return;
                    default:
                        Console.WriteLine(JsonProtocol.Serialize(new { type = "error", message = $"Unknown command: {type}" }));
                        break;
                }
            }
        }
    }

    private static EngineConfig ReadConfig(JsonElement root)
    {
        return new EngineConfig
        {
            IntervalMs = GetDouble(root, "intervalMs", 100),
            Button = GetString(root, "button", "left"),
            DoubleClick = GetBool(root, "doubleClick"),
            JitterEnabled = GetBool(root, "jitterEnabled"),
            JitterRadiusPx = GetInt(root, "jitterRadiusPx", 3),
            RandomIntervalOffsetMinMs = GetInt(root, "randomIntervalOffsetMinMs", 0),
            RandomIntervalOffsetMaxMs = GetInt(root, "randomIntervalOffsetMaxMs", 0),
            HighPrecisionTiming = GetBool(root, "highPrecisionTiming"),
            ProcessPriorityBoost = GetBool(root, "processPriorityBoost"),
            PrecisionMode = GetBool(root, "precisionMode"),
        };
    }

    private static int GetInt(JsonElement root, string name, int fallback)
    {
        return root.TryGetProperty(name, out var value) && value.TryGetInt32(out var parsed)
            ? parsed
            : fallback;
    }

    private static double GetDouble(JsonElement root, string name, double fallback)
    {
        return root.TryGetProperty(name, out var value) && value.TryGetDouble(out var parsed)
            ? parsed
            : fallback;
    }

    private static string GetString(JsonElement root, string name, string fallback)
    {
        return root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? fallback
            : fallback;
    }

    private static bool GetBool(JsonElement root, string name)
    {
        return root.TryGetProperty(name, out var value)
            && (value.ValueKind == JsonValueKind.True || value.ValueKind == JsonValueKind.False)
            && value.GetBoolean();
    }
}
