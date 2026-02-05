import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { AuthService } from "./auth.service";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

@Injectable({
  providedIn: "root",
})
export class ChatService {
  private apiUrl = "/api";

  constructor(private http: HttpClient, private authService: AuthService) { }

  async *streamChat(message: string, threadId: string): AsyncGenerator<string> {
    const response = await fetch(`${this.apiUrl}/chat`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, thread_id: threadId }),
    });

    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (!trimmedLine) continue;

        try {
          const data = JSON.parse(trimmedLine);

          if (data.type === "message") {
            let content = data.content;
            if (content.startsWith("ROUTE:")) {
              content = content.replace(/^ROUTE:.*?REASON:.*?\n?/s, "").trim();
            }

            if (content) yield content;

          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        } catch (e) {
          console.error("JSON Parse Error on line:", trimmedLine, e);
        }
      }
    }
  }

  uploadFile(
    file: File,
    threadId: string,
    description: string = ""
  ): Observable<any> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("thread_id", threadId);
    formData.append("description", description);

    return this.http.post(`${this.apiUrl}/upload`, formData, {
      withCredentials: true,
    });
  }
}