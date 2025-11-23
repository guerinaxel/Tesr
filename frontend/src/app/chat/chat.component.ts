import { Component, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { environment } from '../../environments/environment';

interface ChatMessage {
  id: number;
  from: 'user' | 'assistant';
  content: string;
  isError?: boolean;
}

interface CodeQaResponse {
  answer: string;
  meta?: unknown;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatDividerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent {
  private readonly http = inject(HttpClient);

  @ViewChild('messagesContainer') messagesContainer?: ElementRef<HTMLDivElement>;

  messages: ChatMessage[] = [];
  question = '';
  isSending = false;
  private nextId = 1;

  onSubmit(): void {
    const text = this.question.trim();
    if (!text || this.isSending) {
      return;
    }

    const userMsg: ChatMessage = {
      id: this.nextId++,
      from: 'user',
      content: text,
    };
    this.messages = [...this.messages, userMsg];
    this.question = '';
    this.isSending = true;
    this.scrollToBottom();

    this.http
      .post<CodeQaResponse>(`${environment.apiUrl}/code-qa/`, { question: text })
      .subscribe({
        next: (res) => {
          const aiMsg: ChatMessage = {
            id: this.nextId++,
            from: 'assistant',
            content: res.answer ?? '(empty answer)',
          };
          this.messages = [...this.messages, aiMsg];
          this.finishSending();
          this.scrollToBottom();
        },
        error: (err) => {
          const detail =
            err?.error?.detail ?? 'Erreur lors de la requête à /api/code-qa/.';
          const errorMsg: ChatMessage = {
            id: this.nextId++,
            from: 'assistant',
            content: detail,
            isError: true,
          };
          this.messages = [...this.messages, errorMsg];
          this.finishSending();
          this.scrollToBottom();
        },
      });
  }

  onSpaceSend(event: KeyboardEvent): void {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }

    if (this.isSending) {
      return;
    }

    const text = this.question.trim();
    if (!text) {
      return;
    }

    event.preventDefault();
    this.onSubmit();
  }

  private scrollToBottom(): void {
    const el = this.messagesContainer?.nativeElement;
    if (!el) return;
    setTimeout(() => {
      el.scrollTop = el.scrollHeight;
    }, 0);
  }

  private finishSending(): void {
    setTimeout(() => {
      this.isSending = false;
    }, 200);
  }
}
