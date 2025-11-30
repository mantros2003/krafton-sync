import pygame
import socket
import json
import time
import threading
from collections import deque

# --- CONFIGURATION ---
SERVER_IP = '127.0.0.1'
SERVER_PORT = 5555
LATENCY_DELAY = 0.2
# 100ms buffering for smoothness (Total delay = Latency + Buffer)
INTERPOLATION_OFFSET = 0.1

# --- PYGAME SETUP ---
pygame.init()
WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Krafton Test - Client")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18)

# --- NETWORK CLASSES ---
class NetworkManager:
    """Handles the connection and simulates the 200ms lag on SENDING data"""
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_IP, SERVER_PORT))
        self.sock.setblocking(False)
        
        self.outgoing_queue = deque() # Stores (send_time, data)
        self.incoming_buffer = []     # Stores raw received bytes
        self.running = True

        # Start the thread that manages the simulated lag for sending
        threading.Thread(target=self._send_loop, daemon=True).start()

    def send_input(self, command):
        """Schedule a command to be sent 200ms in the future"""
        send_time = time.time() + LATENCY_DELAY
        self.outgoing_queue.append((send_time, command.encode()))

    def _send_loop(self):
        """Thread that checks queue and actually sends data when time is right"""
        while self.running:
            current_time = time.time()
            if self.outgoing_queue:
                target_time, data = self.outgoing_queue[0]
                if current_time >= target_time:
                    self.outgoing_queue.popleft()
                    try:
                        self.sock.sendall(data)
                    except:
                        self.running = False
                else:
                    time.sleep(0.001)
            else:
                time.sleep(0.001)

    def receive_updates(self):
        """Reads from socket, prints system messages, returns list of new JSON snapshots"""
        try:
            # Basic non-blocking receive
            data = self.sock.recv(4096)
            if not data: return []
            
            # Handling TCP fragmentation (split by newline)
            messages = data.decode('utf-8').strip().split('\n')
            snapshots = []
            
            for msg in messages:
                if not msg.strip(): continue # Skip empty lines
                
                try:
                    msg_obj = json.loads(msg)
                    
                    # Check the Message Type
                    # Use .get() to avoid errors if the key is missing
                    msg_type = msg_obj.get("type", "UNKNOWN")
                    
                    if msg_type == "UPDATE":
                        snapshots.append(msg_obj)
                        
                    elif msg_type == "SYSTEM":
                        content = msg_obj.get("msg", "")
                        if content == "START":
                            print(f"\n{'='*20}\nGAME STARTED!\n{'='*20}\n")
                            
                except json.JSONDecodeError:
                    pass
                    
            return snapshots
            
        except BlockingIOError:
            return []
        except Exception as e:
            print(f"Network Error: {e}")
            return []

class GameState:
    """Stores the latest known world state and handles smoothing"""
    def __init__(self):
        self.snapshots = []
        self.display_players = {}
        self.display_coin = {"x": -100, "y": -100}

    def add_snapshot(self, snapshot):
        """Add new server update to history"""
        self.snapshots.append(snapshot)
        if len(self.snapshots) > 20:
            self.snapshots.pop(0)

    def interpolate(self):
        """Calculate positions for 'Now - InterpolationDelay'"""
        render_time = time.time() - (LATENCY_DELAY + INTERPOLATION_OFFSET)
        
        prev_snap = None
        next_snap = None

        for i in range(len(self.snapshots) - 1):
            if self.snapshots[i]["timestamp"] <= render_time and self.snapshots[i+1]["timestamp"] >= render_time:
                prev_snap = self.snapshots[i]
                next_snap = self.snapshots[i+1]
                break
        
        if prev_snap and next_snap:
            total_time = next_snap["timestamp"] - prev_snap["timestamp"]
            time_passed = render_time - prev_snap["timestamp"]
            ratio = time_passed / total_time
            
            self.display_coin = next_snap["coin"]

            all_ids = set(prev_snap["players"].keys()) | set(next_snap["players"].keys())
            
            for p_id in all_ids:
                if p_id in prev_snap["players"] and p_id in next_snap["players"]:
                    # Lerp Position
                    x1 = prev_snap["players"][p_id]["x"]
                    y1 = prev_snap["players"][p_id]["y"]
                    x2 = next_snap["players"][p_id]["x"]
                    y2 = next_snap["players"][p_id]["y"]
                    
                    curr_x = x1 + (x2 - x1) * ratio
                    curr_y = y1 + (y2 - y1) * ratio
                    
                    self.display_players[p_id] = {
                        "x": curr_x, 
                        "y": curr_y, 
                        "color": next_snap["players"][p_id]["color"],
                        "score": next_snap["players"][p_id]["score"]
                    }
        
        elif self.snapshots:
            latest = self.snapshots[-1]
            self.display_players = latest["players"]
            self.display_coin = latest["coin"]

def main():
    network = NetworkManager()
    game_state = GameState()
    
    running = True
    while running:
        # INPUT HANDLING
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            network.send_input("L")
            print("pressed L")
        if keys[pygame.K_RIGHT]:
            network.send_input("R")
            print("pressed R")
        if keys[pygame.K_UP]:
            network.send_input("U")
            print("pressed U")
        if keys[pygame.K_DOWN]:
            network.send_input("D")
            print("pressed D")

        # NETWORK RECEIVE
        new_snaps = network.receive_updates()
        for snap in new_snaps:
            game_state.add_snapshot(snap)

        # INTERPOLATION
        game_state.interpolate()

        # RENDER
        screen.fill((30, 30, 30))
        
        c = game_state.display_coin
        pygame.draw.circle(screen, (255, 215, 0), (int(c["x"]), int(c["y"])), 15)

        # Draw Players
        for p_id, p_data in game_state.display_players.items():
            color = p_data["color"]
            px, py = int(p_data["x"]), int(p_data["y"])
            pygame.draw.rect(screen, color, (px-20, py-20, 40, 40))
            
            # Draw Score
            score_text = font.render(f"P{p_id[-2:]}: {p_data['score']}", True, (255, 255, 255))
            screen.blit(score_text, (px-20, py-40))

        lag_text = font.render(f"Simulated Latency: {LATENCY_DELAY*1000}ms", True, (255, 255, 255))
        screen.blit(lag_text, (10, 10))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()