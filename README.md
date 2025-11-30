# Krafton Associate Game Developer Assignment: Multiplayer Coin Collector

This repository contains a real-time multiplayer **Coin Collector** game built from scratch using Python.

## 📋 Features

### **Network Simulation**
- A custom latency simulation layer introduces a strict **200ms delay** on all incoming and outgoing packets.

### **Entity Interpolation**
- Clients implement snapshot interpolation to render smooth motion despite heavy network lag.

### **Lobby System**
- The server waits for two clients to connect before auto-starting the session.

### **Reconnection Handling**
- If a player disconnects, the game pauses and returns to the Lobby state.

---

## Tech Stack

- **Language:** Python 3.13
- **Networking:** Raw TCP Sockets (`socket` library)
- **Graphics:** PyGame
- **Protocol:** JSON over TCP

---

## Prerequisites

Install Python and the only external dependency:

```bash
pip install pygame
```

## Run Instructions

### 1. Start the Server
The server will listen for connections and manage the game state.

```bash
python server.py
```

### 2. Start Client 1

```bash
python client.py
```

### 3. Start Client 2

```bash
python client.py
```

## Architecture & Engineering Assumptions
### 1. Latency Simulation (The 200ms Constraint)
To strictly enforce the latency requirement, a middleware queue is implemented on both Client and Server
- Outgoing:
Packets are timestamped and held in a deque until current_time > send_time + 0.2s.
- Incoming:
Even if data arrives physically, processing is delayed until the simulated 200ms lag has passed.

### 2. Entity Interpolation (Smooth Rendering)
Because the client sees the game state 200ms in the past, raw rendering would cause stuttering.
Snapshot Interpolation Implementation:
- Client maintains a buffer of state snapshots.
- Render time = ServerTime - (Latency + Buffer).
- Position (x, y) is linearly interpolated between snapshots surrounding the render timestamp.

Assumption:
A 100ms buffer (total delay ~300ms) ensures a future snapshot always exists for interpolation, eliminating jitter.

###4. Protocol & Formatting
- TCP was chosen over UDP for simpler guaranteed ordering and delivery.
- Framing: Messages are newline-delimited (\n) to handle TCP stream fragmentation.
- Serialization: JSON is used for readability and easy debugging.
