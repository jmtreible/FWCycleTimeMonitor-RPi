using System.ComponentModel.DataAnnotations;

namespace FWCycleDashboard.Data;

public class MachineGroup
{
    public int Id { get; set; }

    [Required]
    [StringLength(100)]
    public string Name { get; set; } = string.Empty;

    [StringLength(500)]
    public string? Description { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public ICollection<Machine> Machines { get; set; } = new List<Machine>();
}
