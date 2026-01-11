import { Component, ElementRef, ViewChild, inject, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, ChatMessage } from '../../core/services/chat.service';
import { AuthService } from '../../core/services/auth.service';
import { marked } from 'marked';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="chat-layout">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h3>Orchestrator</h3>
        </div>
        
        <div class="sidebar-info">
          <div class="info-item">
            <span class="label">Scope</span>
            <span class="value">{{ scope() }}</span>
          </div>
          <div class="info-item">
            <span class="label">Thread ID</span>
            <span class="value code">{{ threadId().slice(0, 8) }}...</span>
          </div>
        </div>

        <div class="sidebar-actions">
           <button class="btn-outline" (click)="clearHistory()">
             🗑️ Clear History
           </button>
           <button class="btn-outline" (click)="logout()">
             🚪 Logout
           </button>
        </div>
      </aside>

      <main class="chat-main">
        <div class="messages-container" #scrollContainer>
          <div *ngIf="messages().length === 0" class="empty-state">
            <div class="icon">👋</div>
            <h2>How can I help you today?</h2>
            <p>You can ask about orders, positions, or upload files.</p>
          </div>

          <div *ngFor="let msg of messages()" 
               class="message-wrapper" 
               [class.user]="msg.role === 'user'">
            <div class="message-bubble">
              <div class="avatar">
                {{ msg.role === 'user' ? '👤' : '🤖' }}
              </div>
              <div class="content" [innerHTML]="renderMarkdown(msg.content)"></div>
            </div>
          </div>

          <div *ngIf="isTyping()" class="typing-indicator">
            <span>Agent is thinking...</span>
            <div class="dots"><span>.</span><span>.</span><span>.</span></div>
          </div>
        </div>

        <div class="input-area">
          <!-- File Staging Area -->
          <div *ngIf="selectedFile()" class="file-staging">
             <div class="file-info">
               <span class="icon">📄</span>
               <span class="name">{{ selectedFile()?.name }}</span>
               <button class="close-btn" (click)="cancelUpload()">✕</button>
             </div>
             <input 
               type="text" 
               [(ngModel)]="fileDescription" 
               placeholder="Add a description for this file..."
               class="description-input"
               (keydown.enter)="confirmUpload()"
             />
             <div class="staging-actions">
               <button class="btn-primary" (click)="confirmUpload()" [disabled]="uploadingFile() !== null">
                 {{ uploadingFile() ? 'Uploading...' : 'Upload & Send' }}
               </button>
             </div>
          </div>

          <!-- Standard Input Area (hidden if staging file?) No, let's keep it visible or hide it. 
               Hiding it avoids confusion. -->
          <div class="input-container" *ngIf="!selectedFile()">
            <button class="attach-btn" (click)="fileInput.click()" title="Upload File">
              📎
            </button>
            <input 
              #fileInput
              type="file" 
              hidden 
              (change)="onFileSelected($event)" 
            />
            
            <textarea 
              [(ngModel)]="newMessage" 
              (keydown.enter)="onEnter($event)"
              placeholder="Type your message here..."
              rows="1"
            ></textarea>
            
            <button class="send-btn" (click)="sendMessage()" [disabled]="!newMessage.trim() || isTyping()">
              ➤
            </button>
          </div>
          <div *ngIf="uploadingFile()" class="upload-status">
            Uploading {{ uploadingFile() }}...
          </div>
        </div>
      </main>
    </div>
  `,
  styleUrls: ['./chat.component.scss']
})
export class ChatComponent {
  private chatService = inject(ChatService);
  private authService = inject(AuthService);

  @ViewChild('scrollContainer') private scrollContainer!: ElementRef;

  messages = signal<ChatMessage[]>([]);
  newMessage = '';
  isTyping = signal(false);
  uploadingFile = signal<string | null>(null);

  // New state for file staging
  selectedFile = signal<File | null>(null);
  fileDescription = '';

  threadId = signal<string>(crypto.randomUUID());
  scope = this.authService.currentUserScope;

  ngOnInit() {
    this.authService.fetchUser();
  }


  constructor() {
    effect(() => {
      this.messages();
      setTimeout(() => this.scrollToBottom(), 100);
    });
  }

  renderMarkdown(content: string): string {
    return marked.parse(content) as string;
  }

  async sendMessage() {
    if (!this.newMessage.trim() || this.isTyping()) return;

    const userMsg = this.newMessage;
    this.newMessage = '';

    this.messages.update(msgs => [...msgs, { role: 'user', content: userMsg }]);
    this.isTyping.set(true);

    try {
      let assistantMsg = '';
      this.messages.update(msgs => [...msgs, { role: 'assistant', content: '' }]);

      for await (const chunk of this.chatService.streamChat(userMsg, this.threadId())) {
        assistantMsg += chunk;
        // Update the last message
        this.messages.update(msgs => {
          const newMsgs = [...msgs];
          newMsgs[newMsgs.length - 1] = { role: 'assistant', content: assistantMsg };
          return newMsgs;
        });
      }
    } catch (err) {
      console.error(err);
      this.messages.update(msgs => [...msgs, { role: 'assistant', content: '❌ Error: Failed to get response.' }]);
    } finally {
      this.isTyping.set(false);
    }
  }

  onEnter(event: Event) {
    if ((event as KeyboardEvent).shiftKey) return;
    event.preventDefault();
    this.sendMessage();
  }

  onFileSelected(event: any) {
    const file = event.target.files[0];
    if (!file) return;

    // Stage the file instead of uploading immediately
    this.selectedFile.set(file);
    this.fileDescription = ''; // Reset description

    // Reset input so validation triggers if same file selected again? 
    // Usually good practice but 'event.target.value = ""' 
    event.target.value = '';
  }

  cancelUpload() {
    this.selectedFile.set(null);
    this.fileDescription = '';
  }

  confirmUpload() {
    const file = this.selectedFile();
    if (!file) return;

    this.uploadingFile.set(file.name);
    // User message showing file + description
    const displayMsg = `📤 Uploaded file: **${file.name}**\n\n> ${this.fileDescription}`;

    this.chatService.uploadFile(file, this.threadId(), this.fileDescription).subscribe({
      next: (res) => {
        this.messages.update(msgs => [...msgs, {
          role: 'user',
          content: displayMsg
        }]);

        if (res.agent_response) {
          this.messages.update(msgs => [...msgs, {
            role: 'assistant',
            content: res.agent_response
          }]);
        }
        this.uploadingFile.set(null);
        this.selectedFile.set(null); // Clear staging
        this.fileDescription = '';
      },
      error: (err) => {
        alert('Upload failed: ' + err.message);
        this.uploadingFile.set(null);
        // Keep staging open on error so they can retry? Or close it?
        // Let's keep it open or just log error.
      }
    });
  }

  clearHistory() {
    this.messages.set([]);
    this.threadId.set(crypto.randomUUID());
  }

  logout() {
    this.authService.logout();
  }

  private scrollToBottom() {
    if (this.scrollContainer) {
      this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
    }
  }
}
