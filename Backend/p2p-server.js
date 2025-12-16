// Simple P2P signaling server for 7KOR.
// Stores a short-lived room with host/client endpoint info for UDP hole punching.

const express = require("express");
const cors = require("cors");
const crypto = require("crypto");

const app = express();
const PORT = process.env.PORT || 3100;
const ROOM_TTL_SECONDS = parseInt(process.env.ROOM_TTL_SECONDS || "900", 10); // 15 minutes
const CLEANUP_INTERVAL_MS = 60 * 1000;

app.use(express.json());
app.use(cors());

const rooms = new Map(); // id -> room

function genId() {
  return crypto.randomBytes(3).toString("hex");
}

function nowSec() {
  return Math.floor(Date.now() / 1000);
}

function cleanup() {
  const cutoff = nowSec() - ROOM_TTL_SECONDS;
  for (const [id, room] of rooms.entries()) {
    if (room.created_at < cutoff) {
      rooms.delete(id);
    }
  }
}
setInterval(cleanup, CLEANUP_INTERVAL_MS).unref();

function remoteIp(req) {
  return req.headers["x-forwarded-for"]?.split(",")[0]?.trim() || req.socket.remoteAddress;
}

app.get("/health", (_req, res) => {
  res.json({ ok: true, rooms: rooms.size });
});

app.post("/rooms", (req, res) => {
  const hostPublicIp = remoteIp(req);
  const hostControlPort = (req.body && req.body.host_control_port) || 50007;
  const hostStatePort = (req.body && req.body.host_state_port) || 50008;
  const hostLocalIp = req.body && req.body.host_local_ip;
  const hostChoice = (req.body && req.body.host_choice) || "rogue";

  const id = genId();
  const room = {
    id,
    created_at: nowSec(),
    host_public_ip: hostPublicIp,
    host_control_port: hostControlPort,
    host_state_port: hostStatePort,
    host_local_ip: hostLocalIp,
    host_local_control_port: hostControlPort,
    host_local_state_port: hostStatePort,
    host_choice: hostChoice,
    client_public_ip: null,
    client_control_port: null,
    client_state_port: null,
    client_local_ip: null,
    client_local_control_port: null,
    client_local_state_port: null,
  };
  rooms.set(id, room);
  res.json(room);
});

app.get("/rooms/:id", (req, res) => {
  const room = rooms.get(req.params.id);
  if (!room) return res.status(404).json({ error: "not found" });
  if (room.created_at < nowSec() - ROOM_TTL_SECONDS) {
    rooms.delete(req.params.id);
    return res.status(404).json({ error: "expired" });
  }
  res.json(room);
});

app.post("/rooms/:id/join", (req, res) => {
  const room = rooms.get(req.params.id);
  if (!room) return res.status(404).json({ error: "not found" });
  if (room.created_at < nowSec() - ROOM_TTL_SECONDS) {
    rooms.delete(req.params.id);
    return res.status(404).json({ error: "expired" });
  }
  room.client_public_ip = remoteIp(req);
  room.client_control_port = (req.body && req.body.client_control_port) || 50007;
  room.client_state_port = (req.body && req.body.client_state_port) || 50008;
  room.client_local_ip = req.body && req.body.client_local_ip;
  room.client_local_control_port = (req.body && req.body.client_control_port) || 50007;
  room.client_local_state_port = (req.body && req.body.client_state_port) || 50008;
  rooms.set(req.params.id, room);
  res.json(room);
});

app.listen(PORT, () => {
  console.log(`P2P signaling server listening on ${PORT}`);
});
