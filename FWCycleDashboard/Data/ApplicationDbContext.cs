using Microsoft.EntityFrameworkCore;

namespace FWCycleDashboard.Data;

public class ApplicationDbContext : DbContext
{
    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
        : base(options)
    {
    }

    public DbSet<Machine> Machines { get; set; }
    public DbSet<MachineGroup> MachineGroups { get; set; }
    public DbSet<CommandHistory> CommandHistory { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<Machine>()
            .HasOne(m => m.Group)
            .WithMany(g => g.Machines)
            .HasForeignKey(m => m.GroupId)
            .OnDelete(DeleteBehavior.SetNull);

        modelBuilder.Entity<CommandHistory>()
            .HasOne(ch => ch.Machine)
            .WithMany()
            .HasForeignKey(ch => ch.MachineId)
            .OnDelete(DeleteBehavior.Cascade);

        // Index for faster queries
        modelBuilder.Entity<Machine>()
            .HasIndex(m => m.MachineId);

        modelBuilder.Entity<CommandHistory>()
            .HasIndex(ch => ch.ExecutedAt);
    }
}
