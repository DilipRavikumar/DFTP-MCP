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
  private apiUrl = "http://localhost:8081/api";

  constructor(private http: HttpClient, private authService: AuthService) {}

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

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          if (data.type === "message") {
            yield data.content;
          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        } catch (e) {
          console.warn("Failed to parse chunk:", line);
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

    // Include credentials to send auth token in cookies
    return this.http.post(`${this.apiUrl}/upload`, formData, {
      withCredentials: true,
    });
  }
}
