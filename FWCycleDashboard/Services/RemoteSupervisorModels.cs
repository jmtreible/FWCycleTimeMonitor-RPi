namespace FWCycleDashboard.Services;

public class ServiceStatusResponse
{
    public string Unit { get; set; } = string.Empty;
    public string? ActiveState { get; set; }
    public string? SubState { get; set; }
    public string? Result { get; set; }
    public int? Pid { get; set; }
    public string? UnitFileState { get; set; }
    public string? StartedAt { get; set; }
    public double? UptimeSeconds { get; set; }
}

public class ConfigResponse
{
    public string MachineId { get; set; } = string.Empty;
    public int GpioPin { get; set; }
    public string CsvPath { get; set; } = string.Empty;
    public int ResetHour { get; set; }
}

public class MetricsResponse
{
    public string MachineId { get; set; } = string.Empty;
    public double? LastCycleSeconds { get; set; }
    public Dictionary<string, double?> WindowAverages { get; set; } = new();
}

public class StackLightState
{
    public bool Green { get; set; }
    public bool Amber { get; set; }
    public bool Red { get; set; }
    public string? LastUpdated { get; set; }
}

public class StackLightSetRequest
{
    public bool Green { get; set; }
    public bool Amber { get; set; }
    public bool Red { get; set; }
}

public class StackLightResponse
{
    public bool Success { get; set; }
    public StackLightState? State { get; set; }
    public string? Message { get; set; }
    public string? Timestamp { get; set; }
    public string? Error { get; set; }
}

public class MachineStatus
{
    public int MachineId { get; set; }
    public string MachineName { get; set; } = string.Empty;
    public bool IsOnline { get; set; }
    public ServiceStatusResponse? Status { get; set; }
    public ConfigResponse? Config { get; set; }
    public MetricsResponse? Metrics { get; set; }
    public StackLightState? StackLight { get; set; }
    public string? Error { get; set; }
    public DateTime LastChecked { get; set; } = DateTime.UtcNow;
}
