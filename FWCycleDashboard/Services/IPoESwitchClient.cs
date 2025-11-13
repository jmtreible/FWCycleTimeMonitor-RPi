namespace FWCycleDashboard.Services;

/// <summary>
/// Interface for controlling PoE switch ports to enable remote power cycling of Raspberry Pis.
/// </summary>
public interface IPoESwitchClient
{
    /// <summary>
    /// Power cycle a specific port (disable, wait, re-enable).
    /// </summary>
    /// <param name="switchIp">IP address of the PoE switch</param>
    /// <param name="portNumber">Port number to power cycle</param>
    /// <param name="waitSeconds">Seconds to wait between disable and enable (default: 3)</param>
    /// <returns>Success status and error message if failed</returns>
    Task<(bool success, string? error)> PowerCyclePortAsync(string switchIp, int portNumber, int waitSeconds = 3);

    /// <summary>
    /// Enable PoE on a specific port.
    /// </summary>
    /// <param name="switchIp">IP address of the PoE switch</param>
    /// <param name="portNumber">Port number to enable</param>
    /// <returns>Success status and error message if failed</returns>
    Task<(bool success, string? error)> EnablePortAsync(string switchIp, int portNumber);

    /// <summary>
    /// Disable PoE on a specific port.
    /// </summary>
    /// <param name="switchIp">IP address of the PoE switch</param>
    /// <param name="portNumber">Port number to disable</param>
    /// <returns>Success status and error message if failed</returns>
    Task<(bool success, string? error)> DisablePortAsync(string switchIp, int portNumber);

    /// <summary>
    /// Get the current PoE status of a port.
    /// </summary>
    /// <param name="switchIp">IP address of the PoE switch</param>
    /// <param name="portNumber">Port number to check</param>
    /// <returns>True if PoE is enabled, false if disabled, null if unknown</returns>
    Task<(bool? enabled, string? error)> GetPortStatusAsync(string switchIp, int portNumber);
}
