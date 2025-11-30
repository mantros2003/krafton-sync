import socket
import threading
import time
import json
import random
import math
from collections import deque

HOST = '127.0.0.1'
PORT = 5555
LATENCY_DELAY = 0.2
MAP_SIZE = 800
PLAYER_SPEED = 5
PLAYER_RADIUS = 20
COIN_RADIUS = 15
REQUIRED_PLAYERS = 2

players = {}
coin = {"x": 400, "y": 300}
connected_clients = []
game_state = "LOBBY_WAITING"

incoming_lag_queue = deque()
outgoing_lag_queue = deque()

def get_random_position():
    return {
        "x": random.randint(50, MAP_SIZE - 50),
        "y": random.randint(50, MAP_SIZE - 50)
    }

def resolve_collision(p_id):
    global coin
    px, py = players[p_id]["x"], players[p_id]["y"]
    cx, cy = coin["x"], coin["y"]
    dist = math.sqrt((px - cx)**2 + (py - cy)**2)
    
    if dist < (PLAYER_RADIUS + COIN_RADIUS):
        players[p_id]["score"] += 1
        coin = get_random_position()
        print(f"Player {p_id} scored! New Score: {players[p_id]['score']}")

def process_game_logic():
    """Main Game Loop: Handles Lobby & Gameplay"""
    global game_state, coin

    print("Server: Waiting for players...")
    
    while True:
        current_time = time.time()
        
        if game_state == "LOBBY_WAITING":
            if len(players) >= REQUIRED_PLAYERS:
                print("Lobby Full. Auto-starting game...")
                game_state = "GAME_RUNNING"
                
                # Broadcast START message
                start_msg = json.dumps({"type": "SYSTEM", "msg": "START"}).encode()
                for sock in connected_clients:
                    try: sock.sendall(start_msg + b'\n')
                    except: pass
            else:
                time.sleep(1)
                continue

        elif game_state == "GAME_RUNNING":
            if len(players) < REQUIRED_PLAYERS:
                print("Player disconnected. Resetting to Lobby...")
                game_state = "LOBBY_WAITING"
                
                incoming_lag_queue.clear()
                outgoing_lag_queue.clear()
                
                for p_id in players:
                    players[p_id]["score"] = 0
                    players[p_id]["x"] = 100
                    players[p_id]["y"] = 100
                
                reset_msg = json.dumps({"type": "SYSTEM", "msg": "RESET"}).encode()
                for sock in connected_clients:
                    try: sock.sendall(reset_msg + b'\n')
                    except:
                        pass
                continue

            while incoming_lag_queue and incoming_lag_queue[0][0] <= current_time:
                _, p_id, data = incoming_lag_queue.popleft()
                
                if p_id not in players: continue
                
                try:
                    cmd = data.decode('utf-8').strip()
                    if cmd == 'L': players[p_id]["x"] -= PLAYER_SPEED
                    elif cmd == 'R': players[p_id]["x"] += PLAYER_SPEED
                    elif cmd == 'U': players[p_id]["y"] -= PLAYER_SPEED
                    elif cmd == 'D': players[p_id]["y"] += PLAYER_SPEED
                    
                    players[p_id]["x"] = max(0, min(MAP_SIZE, players[p_id]["x"]))
                    players[p_id]["y"] = max(0, min(MAP_SIZE, players[p_id]["y"]))
                    resolve_collision(p_id)
                    
                except Exception as e:
                    print(f"Error processing input: {e}")

            state_snapshot = {
                "type": "UPDATE",
                "timestamp": current_time,
                "players": players,
                "coin": coin
            }
            serialized_state = json.dumps(state_snapshot).encode('utf-8')
            
            send_time = current_time + LATENCY_DELAY
            for sock in list(connected_clients):
                 outgoing_lag_queue.append((send_time, sock, serialized_state))

            time.sleep(1/60)

def sender_thread_logic():
    """Dedicated thread to push data out of sockets after delay"""
    while True:
        current_time = time.time()
        
        if outgoing_lag_queue:
            target_time, sock, data = outgoing_lag_queue[0]
            if current_time >= target_time:
                outgoing_lag_queue.popleft()
                try:
                    sock.sendall(data + b'\n') 
                except:
                    if sock in connected_clients:
                        connected_clients.remove(sock)
            else:
                time.sleep(0.001)
        else:
            time.sleep(0.001)

def handle_client_connection(client_socket, addr):
    """Thread per client to receive raw data"""
    print(f"New connection: {addr}")
    p_id = str(addr[1])
    
    connected_clients.append(client_socket)
    players[p_id] = {
        "x": 100 if len(connected_clients) == 1 else 600,
        "y": 100 if len(connected_clients) == 1 else 600, 
        "score": 0, 
        "color": (0, 255, 0) if len(connected_clients) == 1 else (0, 0, 255) # Green vs Blue
    }
    
    try:
        while True:
            data = client_socket.recv(1024)
            if not data: break
            
            # Only accept input if game is running
            if game_state == "GAME_RUNNING":
                process_at = time.time() + LATENCY_DELAY
                incoming_lag_queue.append((process_at, p_id, data))
            
    except ConnectionResetError:
        pass
    finally:
        print(f"Client {addr} disconnected")
        if p_id in players: del players[p_id]
        if client_socket in connected_clients: connected_clients.remove(client_socket)
        client_socket.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(REQUIRED_PLAYERS)
    print(f"Lobby Server listening on {HOST}:{PORT}")
    print(f"Waiting for {REQUIRED_PLAYERS} players to start...")

    # Start Logic Threads
    threading.Thread(target=process_game_logic, daemon=True).start()
    threading.Thread(target=sender_thread_logic, daemon=True).start()

    # Accept Loop
    while True:
        client_sock, addr = server.accept()
        t = threading.Thread(target=handle_client_connection, args=(client_sock, addr))
        t.start()

if __name__ == "__main__":
    main()