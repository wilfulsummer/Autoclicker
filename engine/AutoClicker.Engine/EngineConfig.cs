namespace AutoClicker.Engine;

public sealed class EngineConfig
{
    public double IntervalMs { get; set; } = 100;
    public string Button { get; set; } = "left";
    public bool DoubleClick { get; set; }
    public bool JitterEnabled { get; set; }
    public int JitterRadiusPx { get; set; } = 3;
    public int RandomIntervalOffsetMinMs { get; set; }
    public int RandomIntervalOffsetMaxMs { get; set; }
    public bool HighPrecisionTiming { get; set; }
    public bool ProcessPriorityBoost { get; set; }
    public bool PrecisionMode { get; set; }
}
