import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import mysql from "mysql2/promise";
import { z } from "zod";
import { config } from "dotenv";

config();

const db = await mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  port: Number(process.env.DB_PORT || 3306),
});

const mcp = new McpServer({
  name: "Database MCP Server",
  version: "2.0.0",
});

mcp.tool(
  "nlpQuery",
  "Let the LLM run any English query against the database",
  {
    argsSchema: z.object({ command: z.string() }),
  },
  async (args) => {
    const { command } = args;
    const sql = command;

    try {
      const [rows] = await db.query(sql);
      return {
        content: [{ type: "text", text: JSON.stringify(rows, null, 2) }],
      };
    } catch (error) {
      return { content: [{ type: "text", text: `SQL Error: ${error.message}` }] };
    }
  }
);

const transport = new StdioServerTransport();
await mcp.connect(transport);

console.log("🚀 Database MCP Server running via stdio...");
