import { Component, inject, ViewChild, ElementRef, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';

import { environment } from '../../environments/environment';

interface ChatMessage {
  id: number;
  from: 'user' | 'assistant';
  content: string;
  isError?: boolean;
}

interface TopicSummary {
  id: number;
  name: string;
  message_count: number;
}

interface TopicDetail extends TopicSummary {
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
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
    MatListModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent implements OnInit {
  private readonly http = inject(HttpClient);

  @ViewChild('messagesContainer') messagesContainer?: ElementRef<HTMLDivElement>;

  messages: ChatMessage[] = [];
  question = '';
  systemPrompt: 'code expert' | 'document expert' | 'custom' = 'code expert';
  customPrompt = '';
  isSending = false;
  topics: TopicSummary[] = [];
  selectedTopicId: number | null = null;
  newTopicName = '';
  private pendingTopicSelection: number | null = null;
  private nextId = 1;

  ngOnInit(): void {
    this.loadTopics();
  }

  onSubmit(): void {
    if (this.isSending) {
      return;
    }

    const text = this.question.trim();
    if (!text) {
      return;
    }

    if (this.systemPrompt === 'custom' && !this.customPrompt.trim()) {
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

    const payload: Record<string, string> = {
      question: text,
      system_prompt: this.systemPrompt,
    };

    if (this.selectedTopicId) {
      payload.topic_id = String(this.selectedTopicId);
    }

    if (this.systemPrompt === 'custom') {
      payload.custom_prompt = this.customPrompt.trim();
    }

    this.http
      .post<CodeQaResponse>(`${environment.apiUrl}/code-qa/`, payload)
      .subscribe({
        next: (res) => {
          const aiMsg: ChatMessage = {
            id: this.nextId++,
            from: 'assistant',
            content: res.answer ?? '(empty answer)',
          };
          this.messages = [...this.messages, aiMsg];
          this.finishSending();
          this.refreshTopicMetadata(this.selectedTopicId);
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

  loadTopics(selectTopicId: number | null = null): void {
    this.http
      .get<{ topics: TopicSummary[] }>(`${environment.apiUrl}/topics/`)
      .subscribe({
        next: (res) => {
          this.topics = (res.topics ?? []).sort((a, b) => a.id - b.id);

          const desiredTopicId =
            selectTopicId ?? this.pendingTopicSelection ?? this.selectedTopicId;
          const topicExists = desiredTopicId
            ? this.topics.some((entry) => entry.id === desiredTopicId)
            : false;

          if (topicExists && desiredTopicId != null) {
            this.pendingTopicSelection = null;
            this.selectTopic(desiredTopicId);
            return;
          }

          if (this.topics.length) {
            this.pendingTopicSelection = null;
            this.selectTopic(this.topics[this.topics.length - 1].id);
            return;
          }

          this.selectedTopicId = null;
          this.messages = [];
        },
        error: () => {
          this.topics = [];
          this.selectedTopicId = null;
          this.messages = [];
        },
      });
  }

  selectTopic(topicId: number): void {
    if (this.selectedTopicId === topicId) {
      return;
    }

    this.selectedTopicId = topicId;
    this.http
      .get<TopicDetail>(`${environment.apiUrl}/topics/${topicId}/`)
      .subscribe({
        next: (res) => {
          this.nextId = 1;
          this.messages = res.messages.map((msg) => ({
            id: this.nextId++,
            from: msg.role,
            content: msg.content,
          }));
          this.scrollToBottom();
        },
        error: () => {
          this.messages = [];
        },
      });
  }

  createTopic(): void {
    const name = this.newTopicName.trim();
    if (!name) {
      return;
    }

    this.http
      .post<TopicDetail>(`${environment.apiUrl}/topics/`, { name })
      .subscribe({
        next: (topic) => {
          this.newTopicName = '';
          this.pendingTopicSelection = topic.id;
          this.selectTopic(topic.id);
          this.loadTopics(topic.id);
        },
      });
  }

  private refreshTopicMetadata(topicId: number | null): void {
    if (!topicId) return;

    this.http
      .get<TopicDetail>(`${environment.apiUrl}/topics/${topicId}/`)
      .subscribe({
        next: (topic) => {
          this.topics = this.topics.map((entry) =>
            entry.id === topic.id
              ? { id: topic.id, name: topic.name, message_count: topic.message_count }
              : entry
          );
        },
      });
  }
}
