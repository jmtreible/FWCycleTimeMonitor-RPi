using System.Net.Http.Headers;
using System.Text.Json;
using FWCycleDashboard.Data;

namespace FWCycleDashboard.Services;

public class RemoteSupervisorClient
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<RemoteSupervisorClient> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public RemoteSupervisorClient(
        IHttpClientFactory httpClientFactory,
        ILogger<RemoteSupervisorClient> logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
        };
    }

    private HttpClient CreateClient(Machine machine)
    {
        var client = _httpClientFactory.CreateClient("RemoteSupervisor");
        var protocol = machine.UseHttps ? "https" : "http";
        client.BaseAddress = new Uri($"{protocol}://{machine.IpAddress}:{machine.Port}");
        client.DefaultRequestHeaders.Add("X-API-Key", machine.ApiKey);
        client.Timeout = TimeSpan.FromSeconds(10);
        return client;
    }

    public async Task<ServiceStatusResponse?> GetStatusAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.GetAsync("/service/status");
            response.EnsureSuccessStatusCode();
            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<ServiceStatusResponse>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get status from machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return null;
        }
    }

    public async Task<ConfigResponse?> GetConfigAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.GetAsync("/config");
            response.EnsureSuccessStatusCode();
            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<ConfigResponse>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get config from machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return null;
        }
    }

    public async Task<MetricsResponse?> GetMetricsAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.GetAsync("/metrics/summary");
            response.EnsureSuccessStatusCode();
            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<MetricsResponse>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get metrics from machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return null;
        }
    }

    public async Task<(bool Success, string? Error)> StartServiceAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.PostAsync("/service/start", null);
            response.EnsureSuccessStatusCode();
            return (true, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start service on machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<(bool Success, string? Error)> StopServiceAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.PostAsync("/service/stop", null);
            response.EnsureSuccessStatusCode();
            return (true, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to stop service on machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<(bool Success, string? Error)> RestartServiceAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.PostAsync("/service/restart", null);
            response.EnsureSuccessStatusCode();
            return (true, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to restart service on machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<(bool Success, string? Error)> RebootPiAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.PostAsync("/system/reboot", null);
            response.EnsureSuccessStatusCode();
            return (true, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to reboot machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<StackLightState?> GetStackLightStatusAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.GetAsync("/stacklight/status");
            response.EnsureSuccessStatusCode();
            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<StackLightState>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get stack light status from machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return null;
        }
    }

    public async Task<(bool Success, string? Error)> SetStackLightAsync(
        Machine machine,
        bool green,
        bool amber,
        bool red)
    {
        try
        {
            using var client = CreateClient(machine);
            var request = new StackLightSetRequest
            {
                Green = green,
                Amber = amber,
                Red = red
            };
            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var response = await client.PostAsync("/stacklight/set", content);
            response.EnsureSuccessStatusCode();

            var responseJson = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<StackLightResponse>(responseJson, _jsonOptions);

            if (result?.Success == true)
            {
                return (true, null);
            }
            else
            {
                return (false, result?.Error ?? "Unknown error");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set stack light on machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<(bool Success, string? Error)> TestStackLightAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.PostAsync("/stacklight/test", null);
            response.EnsureSuccessStatusCode();

            var responseJson = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<StackLightResponse>(responseJson, _jsonOptions);

            if (result?.Success == true)
            {
                return (true, null);
            }
            else
            {
                return (false, result?.Error ?? "Unknown error");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to test stack light on machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<(bool Success, string? Error)> TurnOffStackLightAsync(Machine machine)
    {
        try
        {
            using var client = CreateClient(machine);
            var response = await client.PostAsync("/stacklight/off", null);
            response.EnsureSuccessStatusCode();

            var responseJson = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<StackLightResponse>(responseJson, _jsonOptions);

            if (result?.Success == true)
            {
                return (true, null);
            }
            else
            {
                return (false, result?.Error ?? "Unknown error");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to turn off stack light on machine {MachineId} at {IpAddress}",
                machine.MachineId, machine.IpAddress);
            return (false, ex.Message);
        }
    }

    public async Task<MachineStatus> GetFullStatusAsync(Machine machine)
    {
        var status = new MachineStatus
        {
            MachineId = machine.Id,
            MachineName = machine.MachineId,
            LastChecked = DateTime.UtcNow
        };

        try
        {
            status.Status = await GetStatusAsync(machine);
            status.Config = await GetConfigAsync(machine);
            status.Metrics = await GetMetricsAsync(machine);
            status.StackLight = await GetStackLightStatusAsync(machine);
            status.IsOnline = status.Status != null;
        }
        catch (Exception ex)
        {
            status.IsOnline = false;
            status.Error = ex.Message;
            _logger.LogError(ex, "Failed to get full status from machine {MachineId}", machine.MachineId);
        }

        return status;
    }
}
