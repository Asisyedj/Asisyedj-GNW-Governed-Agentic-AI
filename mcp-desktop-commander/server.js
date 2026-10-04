import http from "node:http";

const UPSTREAM = "https://mcp.desktopcommander.app";
const CANONICAL_RESOURCE = "https://mcp.desktopcommander.app/mcp";

function upstreamUrl(req) {
  const incoming = new URL(req.url || "/", `https://${req.headers.host || "bridge.invalid"}`);
  if (incoming.searchParams.has("resource")) {
    incoming.searchParams.set("resource", CANONICAL_RESOURCE);
  }
  return UPSTREAM + incoming.pathname + incoming.search;
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Authorization,Content-Type,Accept,Mcp-Protocol-Version,Mcp-Session-Id,Last-Event-ID",
    "Access-Control-Expose-Headers": "Location,WWW-Authenticate,Mcp-Session-Id",
  };
}

const server = http.createServer((req, res) => {
  if (req.method === "OPTIONS") {
    res.writeHead(204, corsHeaders());
    return res.end();
  }

  const chunks = [];
  req.on("data", chunk => chunks.push(chunk));
  req.on("end", async () => {
    try {
      const headers = { ...req.headers };
      delete headers.host;
      delete headers.connection;
      delete headers["content-length"];
      delete headers["transfer-encoding"];

      const body = req.method === "GET" || req.method === "HEAD" ? undefined : Buffer.concat(chunks);
      const upstream = await fetch(upstreamUrl(req), {
        method: req.method,
        headers,
        body,
        redirect: "manual",
      });

      const outHeaders = { ...corsHeaders() };
      upstream.headers.forEach((value, key) => {
        const lower = key.toLowerCase();
        if (!["connection", "transfer-encoding", "content-encoding", "content-length"].includes(lower)) {
          outHeaders[key] = value;
        }
      });

      res.writeHead(upstream.status, outHeaders);
      if (!upstream.body) return res.end();

      const reader = upstream.body.getReader();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        res.write(Buffer.from(value));
      }
      res.end();
    } catch (error) {
      const payload = JSON.stringify({
        error: "proxy_error",
        message: error instanceof Error ? error.message : String(error),
      });
      res.writeHead(502, { ...corsHeaders(), "Content-Type": "application/json" });
      res.end(payload);
    }
  });
});

server.listen(process.env.PORT || 3000, "0.0.0.0", () => {
  console.log(`Desktop Commander MCP bridge listening on ${process.env.PORT || 3000}`);
});
