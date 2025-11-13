using System.ComponentModel.DataAnnotations;

namespace FWCycleDashboard.Data;

public class Machine
{
    public int Id { get; set; }

    [Required]
    [StringLength(50)]
    public string MachineId { get; set; } = string.Empty;

    [Required]
    [StringLength(100)]
    public string IpAddress { get; set; } = string.Empty;

    [Required]
    public int Port { get; set; } = 8443;

    [Required]
    [StringLength(200)]
    public string ApiKey { get; set; } = string.Empty;

    [StringLength(200)]
    public string? Location { get; set; }

    [StringLength(500)]
    public string? Description { get; set; }

    public int? GroupId { get; set; }
    public MachineGroup? Group { get; set; }

    public bool UseHttps { get; set; } = false;

    // PoE Switch Configuration for Remote Boot
    [StringLength(100)]
    public string? PoESwitchIp { get; set; }

    public int? PoESwitchPort { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? LastSeenAt { get; set; }

    // Cached status from last check
    public string? LastStatus { get; set; }
    public string? LastError { get; set; }
}
