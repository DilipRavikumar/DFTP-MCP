import mysql from "mysql2/promise";
import dotenv from "dotenv";

dotenv.config();

export const connection = await mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  port: process.env.DB_PORT || 3306,
});

export async function getTasks() {
  const [rows] = await connection.query("SELECT * FROM task");
  return rows;
}

export async function addTask(title, description) {
  const [result] = await connection.query(
    "INSERT INTO task (title, description) VALUES (?, ?)",
    [title, description]
  );
  return result.insertId;
}

export async function deleteTask(id) {
  const [result] = await connection.query(
    "DELETE FROM task WHERE id = ?",
    [id]
  );
  return result.affectedRows;
}
