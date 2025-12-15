// Simple lobby server for 7KOR online matches.
// Stores lobbies in memory; intended to be kept running under pm2.

const express = require("express");
const cors = require("cors");
const crypto = require("crypto");
const dgram = require("dgram");

const app = express();
const PORT = process.env.PORT || 3000;
const RELAY_CONTROL_PORT = parseInt(process.env.RELAY_CONTROL_PORT || "40007", 10);
const RELAY_STATE_PORT = parseInt(process.env.RELAY_STATE_PORT || "40008", 10);
const PUBLIC_HOST = process.env.PUBLIC_HOST; // optional override for advertised relay host
const LOBBY_TTL_SECONDS = parseInt(process.env.LOBBY_TTL_SECONDS || "3600", 10);
const CLEANUP_INTERVAL_MS = 60 * 1000;

app.use(express.json());
app.use(cors());

const lobbies = new Map(); // id -> {host_ip, control_port, state_port, created_at, host_choice}
const relayHostControl = new Map(); // lobby -> {address, port, last}
const relayClientsState = new Map(); // lobby -> Map(endpointKey, {address, port, last})

function generateLobbyId() {
  return crypto.randomBytes(3).toString("hex"); // 6 hex chars
}

function advertisedHost(req) {
  if (PUBLIC_HOST) return PUBLIC_HOST;
  if (req.headers && req.headers.host) {
    return req.headers.host.split(":")[0];
  }
  if (req.hostname) return req.hostname;
  return "localhost";
}

function nowSeconds() {
  return Math.floor(Date.now() / 1000);
}

function cleanupExpired() {
  const cutoff = nowSeconds() - LOBBY_TTL_SECONDS;
  for (const [id, lobby] of lobbies.entries()) {
    if (lobby.created_at < cutoff) {
      lobbies.delete(id);
    }
  }
}
setInterval(cleanupExpired, CLEANUP_INTERVAL_MS).unref();

app.get("/health", (_req, res) => {
  res.json({ ok: true, lobbies: lobbies.size });
});

app.post("/lobbies", (req, res) => {
  const hostIp =
    (req.body && req.body.host_ip) ||
    req.headers["x-forwarded-for"] ||
    req.socket.remoteAddress;
  const controlPort = (req.body && req.body.control_port) || 50007;
  const statePort = (req.body && req.body.state_port) || 50008;
  const hostChoice = (req.body && req.body.host_choice) || "rogue";
  if (!hostIp) {
    return res.status(400).json({ error: "host_ip is required" });
  }
  const id = generateLobbyId();
  lobbies.set(id, {
    host_ip: hostIp,
    control_port: controlPort,
    state_port: statePort,
    host_choice: hostChoice,
    created_at: nowSeconds(),
  });
  res.json({
    id,
    host_ip: hostIp,
    control_port: controlPort,
    state_port: statePort,
    host_choice: hostChoice,
    relay_host: advertisedHost(req),
    relay_control_port: RELAY_CONTROL_PORT,
    relay_state_port: RELAY_STATE_PORT,
  });
});

app.get("/lobbies/:id", (req, res) => {
  const lobby = lobbies.get(req.params.id);
  if (!lobby) {
    return res.status(404).json({ error: "not found" });
  }
  if (lobby.created_at < nowSeconds() - LOBBY_TTL_SECONDS) {
    lobbies.delete(req.params.id);
    return res.status(404).json({ error: "expired" });
  }
  res.json(lobby);
});

app.delete("/lobbies/:id", (req, res) => {
  lobbies.delete(req.params.id);
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`Lobby server listening on ${PORT}`);
});

// --- UDP relay setup ---
const controlRelay = dgram.createSocket("udp4");
const stateRelay = dgram.createSocket("udp4");

function keyFromRinfo(rinfo) {
  return `${rinfo.address}:${rinfo.port}`;
}

controlRelay.on("message", (msg, rinfo) => {
  let payload;
  try {
    payload = JSON.parse(msg.toString());
  } catch (err) {
    return;
  }
  if (!payload || !payload.lobby) return;
  const lobby = payload.lobby;
  // Host registers for control
  if (payload.role === "host") {
    relayHostControl.set(lobby, { address: rinfo.address, port: rinfo.port, last: Date.now() });
    return;
  }
  // Client sends control payload -> forward to host
  if (payload.role === "client" && payload.payload) {
    const host = relayHostControl.get(lobby);
    if (!host) return;
    const buf = Buffer.from(JSON.stringify(payload.payload));
    controlRelay.send(buf, host.port, host.address);
  }
});

stateRelay.on("message", (msg, rinfo) => {
  let payload;
  try {
    payload = JSON.parse(msg.toString());
  } catch (err) {
    return;
  }
  if (!payload || !payload.lobby) return;
  const lobby = payload.lobby;
  // Client registers to receive state
  if (payload.role === "client" && payload.type === "register") {
    const set = relayClientsState.get(lobby) || new Map();
    set.set(keyFromRinfo(rinfo), { address: rinfo.address, port: rinfo.port, last: Date.now() });
    relayClientsState.set(lobby, set);
    return;
  }
  // Host pushes state payload -> broadcast to registered clients
  if (payload.role === "host" && payload.payload) {
    const clients = relayClientsState.get(lobby);
    if (!clients || clients.size === 0) return;
    const buf = Buffer.from(JSON.stringify(payload.payload));
    for (const { address, port } of clients.values()) {
      stateRelay.send(buf, port, address);
    }
  }
});

function cleanupRelayMaps() {
  const cutoff = Date.now() - LOBBY_TTL_SECONDS * 1000;
  for (const [lobby, host] of relayHostControl.entries()) {
    if (host.last < cutoff) relayHostControl.delete(lobby);
  }
  for (const [lobby, clients] of relayClientsState.entries()) {
    for (const [key, entry] of clients.entries()) {
      if (entry.last < cutoff) clients.delete(key);
    }
    if (clients.size === 0) relayClientsState.delete(lobby);
  }
}
setInterval(cleanupRelayMaps, CLEANUP_INTERVAL_MS).unref();

controlRelay.bind(RELAY_CONTROL_PORT, () => {
  console.log(`Control relay listening on UDP ${RELAY_CONTROL_PORT}`);
});
stateRelay.bind(RELAY_STATE_PORT, () => {
  console.log(`State relay listening on UDP ${RELAY_STATE_PORT}`);
});
