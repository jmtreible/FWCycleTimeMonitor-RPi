# PoE Switch Recommendations for Remote Boot Control

## Your Requirements
- **Machine Count:** 32 + 13 = 45 Raspberry Pis total
- **Budget:** ~$250 per switch
- **Must Have:** Managed PoE with API/SNMP control for remote power cycling
- **Source:** Amazon preferred

---

## Reality Check: 32-Port Challenge

**Important Finding:** True 32-port managed PoE switches with API control under $250 **do not exist** on Amazon in 2025.

**Why:**
- 32-port is an uncommon size (manufacturers make 24, 28, or 48-port models)
- Managed switches with API/SNMP typically cost $400-600+ for 32+ ports
- Budget options (<$250) are mostly unmanaged or "Easy Smart" (limited API)

---

## Recommended Solutions

### Option 1: TP-Link JetStream 28-Port (Best Match) ⭐

**Model:** TP-Link TL-SG3428MP or SG3428MP (newer version)

**Specs:**
- **Ports:** 28 total (24× PoE+ ports + 4× SFP)
- **PoE Budget:** 384W (16W per port typical)
- **Management:** Full L2+ managed with API/SNMP/CLI/Web
- **Price:** ~$280-$350 on Amazon
- **API Support:** Yes - SNMP v1/v2/v3, CLI (SSH/Telnet), REST API via Omada

**For Your Setup:**
- **Switch 1:** Handle 24 machines (uses 24 PoE ports)
- **Switch 2:** Handle 21 machines (uses 21 of 24 PoE ports)
- **Total:** 2 switches for 45 machines

**Pros:**
- ✅ Full API control via SNMP
- ✅ Omada SDN integration (cloud management)
- ✅ Proven reliability
- ✅ 5-year warranty
- ✅ Easy to configure

**Cons:**
- ❌ Slightly over budget ($280-350 vs $250)
- ❌ Need 2 switches instead of original plan

**Amazon Link:** Search "TP-Link TL-SG3428MP" or "TP-Link SG3428MP"

---

### Option 2: TP-Link 16-Port + 16-Port (Budget Option)

**Model:** TP-Link TL-SG1016PE (16-port Easy Smart)

**Specs:**
- **Ports:** 16 total (8× PoE+ ports, 8× non-PoE)
- **PoE Budget:** 150W total
- **Management:** Easy Smart (web-based, limited SNMP)
- **Price:** ~$120-150 each on Amazon

**For Your Setup:**
- **Switch 1:** 2× 16-port switches = 32 ports (16 PoE each = 32 PoE total) → 32 machines
- **Switch 2:** 1× 16-port switch = 16 ports (8 PoE) → 8 machines
- **Additional:** 5 more machines need solution (see workaround below)

**Pros:**
- ✅ Well under budget ($360-450 total for 3 switches)
- ✅ Available on Amazon
- ✅ Simple management

**Cons:**
- ❌ "Easy Smart" has limited API (web interface mainly, basic SNMP only)
- ❌ Only 8 PoE ports per switch (need multiple switches)
- ❌ Lower PoE budget per switch
- ❌ More physical switches to manage

**Amazon Link:** Search "TP-Link TL-SG1016PE"

---

### Option 3: Hybrid Approach (Most Economical)

**Combination:**
- 1× TP-Link TL-SG3428MP (28-port, full managed) - ~$300
- 1× TP-Link TL-SG1016PE (16-port, Easy Smart) - ~$130
- 1× TP-Link TL-SG1016PE (16-port, Easy Smart) - ~$130

**Total:** ~$560 for all three switches

**Coverage:**
- Switch 1 (28-port): 24 machines with full API control
- Switch 2 (16-port): 8 machines with basic web control
- Switch 3 (16-port): 8 machines with basic web control
- **Additional:** 5 machines need alternative (see below)

**For Your 32 + 13 Setup:**
- **Group 1 (32 machines):**
  - 24 on TL-SG3428MP (full API)
  - 8 on TL-SG1016PE (web control)
- **Group 2 (13 machines):**
  - 8 on second TL-SG1016PE (web control)
  - 5 need alternative power control

---

### Option 4: Go Slightly Over Budget (Best Long-Term)

**Model:** TP-Link TL-SG3452P (52-port, 48× PoE)

**Specs:**
- **Ports:** 52 total (48× PoE+ ports + 4× SFP+)
- **PoE Budget:** 384W
- **Management:** Full L2+ managed with API/SNMP/CLI
- **Price:** ~$550-650

**For Your Setup:**
- **One Switch:** Handles all 45 machines with 3 ports to spare
- **Centralized:** Single switch, single API endpoint

**Pros:**
- ✅ Single switch for everything
- ✅ Full API control for all ports
- ✅ Simplest configuration
- ✅ Room for growth

**Cons:**
- ❌ Over budget ($550-650 vs $500 total)
- ❌ Overkill for 13-machine location

---

## API Control Comparison

| Switch Model | SNMP | REST API | SSH/CLI | Web GUI | Power Cycle API |
|--------------|------|----------|---------|---------|-----------------|
| **TL-SG3428MP** | ✅ v1/v2/v3 | ✅ via Omada | ✅ Yes | ✅ Yes | ✅ Yes |
| **TL-SG1016PE** | ⚠️ Limited | ❌ No | ❌ No | ✅ Yes | ⚠️ Via web scraping |
| **TL-SG3452P** | ✅ v1/v2/v3 | ✅ via Omada | ✅ Yes | ✅ Yes | ✅ Yes |

---

## My Recommendation

### For 32 Machines:
**Buy:** 2× TP-Link TL-SG3428MP (28-port each)
- **Cost:** ~$600-700 total
- **Coverage:** 48 PoE ports (more than enough for 32 machines)
- **Control:** Full API control via SNMP or Omada for all machines

### For 13 Machines:
**Buy:** 1× TP-Link TL-SG1016PE (16-port)
- **Cost:** ~$130
- **Coverage:** 8 PoE ports for direct power cycling
- **Control:** Web-based management + basic SNMP

**For remaining 5 machines:** Use Solution 3 (don't shutdown, just reboot)

### Total Investment: ~$730-830
- Over your original $500 budget, but provides full remote control
- All 40 machines (32+8) have API-controlled power cycling
- 5 machines can still be rebooted remotely, just not cold-booted

---

## Alternative: Stay Under Budget with Compromises

### Budget Option (~$390 total):
- 2× TP-Link TL-SG1016PE for 32 machines (~$260)
- 1× TP-Link TL-SG1016PE for 13 machines (~$130)
- **Total:** 48 ports (24 PoE)

### Compromises:
- Limited API control (web scraping or manual control required)
- Only 24 total PoE ports (need non-PoE Pis or alternative power for 21 machines)
- Basic management features

**Workaround for non-PoE ports:**
- Use PoE injectors ($10-15 each) for non-PoE switch ports
- Or use GPIO wake solution (Solution 2 from previous doc) for ~$5/machine

---

## Purchase Links (Amazon)

### Recommended Models:

1. **TP-Link TL-SG3428MP (28-port)**
   - Search: "TP-Link TL-SG3428MP JetStream"
   - Or: "TP-Link SG3428MP" (newer version)
   - Price: ~$280-350

2. **TP-Link TL-SG1016PE (16-port)**
   - Search: "TP-Link TL-SG1016PE 16-Port PoE"
   - Price: ~$120-150

3. **TP-Link TL-SG3452P (52-port)** (if going over budget)
   - Search: "TP-Link TL-SG3452P JetStream"
   - Price: ~$550-650

---

## Implementation Plan

### Phase 1: Purchase (Choose One)

**Option A - Full API Control (Recommended):**
- 2× TL-SG3428MP for main location (32 machines → use 24+8 ports)
- 1× TL-SG1016PE for secondary location (13 machines → use 8 PoE ports)

**Option B - Budget Conscious:**
- 3× TL-SG1016PE total
- Implement web-based control instead of API

### Phase 2: Network Setup
1. Install switches in rack/location
2. Configure management IP addresses
3. Set up SNMP community strings or Omada accounts
4. Map each Pi to specific switch port number

### Phase 3: Dashboard Integration
1. Add switch configuration to dashboard (I'll implement this)
2. Configure port mappings in database
3. Add "Boot" button to dashboard UI
4. Test power cycle functionality

### Phase 4: Testing
1. Test power cycle on one Pi
2. Verify Pi boots after power cycle
3. Roll out to all machines

---

## Configuration Data Needed (After Purchase)

Once you buy the switches, I'll need:

1. **Switch Model(s):** Exact model numbers purchased
2. **Management IPs:** What IP address is each switch?
3. **Credentials:** Admin username/password for API access
4. **Port Mappings:** Which Pi is connected to which port on which switch?

Example:
```
Switch 1 (192.168.1.10 - TL-SG3428MP):
- Machine "Press-01" → Port 1
- Machine "Press-02" → Port 2
- Machine "Press-03" → Port 3
...

Switch 2 (192.168.1.11 - TL-SG3428MP):
- Machine "Mold-01" → Port 1
...
```

---

## Summary Table

| Solution | Total Cost | API Control | Coverage | Complexity |
|----------|------------|-------------|----------|------------|
| **2× 28-port (Recommended)** | ~$600-700 | ✅ Full | 48 ports (45 needed) | Medium |
| **1× 52-port** | ~$550-650 | ✅ Full | 48 PoE ports | Low |
| **3× 16-port** | ~$360-450 | ⚠️ Limited | 24 PoE ports | High |
| **Hybrid (28+16+16)** | ~$560 | ⚠️ Mixed | 40 PoE + 8 non-PoE | High |

---

## Next Steps

1. **Decide on budget:** Stick to ~$500 or go to ~$700 for full control?
2. **Choose configuration:** Which option above?
3. **Purchase switches** from Amazon
4. **Share details** with me: model, IPs, credentials
5. **I'll implement** the switch control in dashboard

**What's your decision?** I recommend the 2× 28-port option for best long-term solution!
