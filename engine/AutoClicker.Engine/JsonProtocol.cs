using System.Text.Json;
using System.Text.Json.Serialization;

namespace AutoClicker.Engine;

public static class JsonProtocol
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public static string Serialize(object payload)
    {
        return JsonSerializer.Serialize(payload, Options);
    }

    public static JsonDocument? Parse(string? line)
    {
        if (string.IsNullOrWhiteSpace(line))
        {
            return null;
        }

        try
        {
            return JsonDocument.Parse(line);
        }
        catch
        {
            return null;
        }
    }
}
