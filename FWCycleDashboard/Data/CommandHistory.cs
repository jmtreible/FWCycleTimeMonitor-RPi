using System.ComponentModel.DataAnnotations;

namespace FWCycleDashboard.Data;

public class CommandHistory
{
    public int Id { get; set; }

    public int MachineId { get; set; }
    public Machine Machine { get; set; } = null!;

    [Required]
    [StringLength(50)]
    public string Command { get; set; } = string.Empty;

    public DateTime ExecutedAt { get; set; } = DateTime.UtcNow;

    public bool Success { get; set; }

    [StringLength(2000)]
    public string? Response { get; set; }

    [StringLength(2000)]
    public string? Error { get; set; }
}
