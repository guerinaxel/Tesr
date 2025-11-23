import {
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  computed,
  inject,
  input,
  model,
  output,
  signal,
} from '@angular/core';
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

  readonly initialTopicId = input<number | null>(null);
  readonly messageSent = output<ChatMessage>();

  @ViewChild('messagesContainer') messagesContainer?: ElementRef<HTMLDivElement>;

  readonly messages = signal<ChatMessage[]>([]);
  readonly question = model('');
  readonly systemPrompt = model<'code expert' | 'document expert' | 'custom'>(
    'code expert'
  );
  readonly customPrompt = model('');
  readonly isSending = signal(false);
  readonly topics = signal<TopicSummary[]>([]);
  readonly selectedTopicId = signal<number | null>(null);
  readonly newTopicName = model('');
  private pendingTopicSelection: number | null = null;
  private nextId = 1;

  readonly hasTopics = computed(() => this.topics().length > 0);
  readonly hasMessages = computed(() => this.messages().length > 0);
  readonly isCustomPrompt = computed(() => this.systemPrompt() === 'custom');
  readonly emptyStateText = computed(() =>
    this.selectedTopicId()
      ? "Commencez la conversation pour obtenir de l'aide sur votre projet."
      : 'Sélectionnez ou créez un topic pour démarrer.'
  );
  readonly sendingLabel = computed(() =>
    this.isSending() ? 'Envoi...' : 'Envoyer'
  );

  ngOnInit(): void {
    this.loadTopics(this.initialTopicId());
  }

  onSubmit(): void {
    if (this.isSending()) {
      return;
    }

    const text = this.question().trim();
    if (!text) {
      return;
    }

    if (this.isCustomPrompt() && !this.customPrompt().trim()) {
      return;
    }

    const userMsg: ChatMessage = {
      id: this.nextId++,
      from: 'user',
      content: text,
    };
    this.messages.update((msgs) => [...msgs, userMsg]);
    this.messageSent.emit(userMsg);
    this.question.set('');
    this.isSending.set(true);
    this.scrollToBottom();

    const payload: Record<string, string> = {
      question: text,
      system_prompt: this.systemPrompt(),
    };

    if (this.selectedTopicId()) {
      payload.topic_id = String(this.selectedTopicId());
    }

    if (this.isCustomPrompt()) {
      payload.custom_prompt = this.customPrompt().trim();
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
          this.messages.update((msgs) => [...msgs, aiMsg]);
          this.finishSending();
          this.refreshTopicMetadata(this.selectedTopicId());
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
          this.messages.update((msgs) => [...msgs, errorMsg]);
          this.finishSending();
          this.scrollToBottom();
        },
      });
  }

  onSpaceSend(event: KeyboardEvent): void {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }

    if (this.isSending()) {
      return;
    }

    const text = this.question().trim();
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
      this.isSending.set(false);
    }, 200);
  }

  loadTopics(selectTopicId: number | null = null): void {
    this.http
      .get<{ topics: TopicSummary[] }>(`${environment.apiUrl}/topics/`)
      .subscribe({
        next: (res) => {
          this.topics.set((res.topics ?? []).sort((a, b) => a.id - b.id));

          const desiredTopicId =
            selectTopicId ?? this.pendingTopicSelection ?? this.selectedTopicId();
          const topicExists = desiredTopicId
            ? this.topics().some((entry) => entry.id === desiredTopicId)
            : false;

          if (topicExists && desiredTopicId != null) {
            this.pendingTopicSelection = null;
            this.selectTopic(desiredTopicId);
            return;
          }

          if (this.topics().length) {
            this.pendingTopicSelection = null;
            const entries = this.topics();
            this.selectTopic(entries[entries.length - 1].id);
            return;
          }

          this.selectedTopicId.set(null);
          this.messages.set([]);
        },
        error: () => {
          this.topics.set([]);
          this.selectedTopicId.set(null);
          this.messages.set([]);
        },
      });
  }

  selectTopic(topicId: number, force = false): void {
    if (this.selectedTopicId() === topicId && !force) {
      return;
    }

    this.selectedTopicId.set(topicId);
    this.http
      .get<TopicDetail>(`${environment.apiUrl}/topics/${topicId}/`)
      .subscribe({
        next: (res) => {
          this.nextId = 1;
          this.messages.set(
            res.messages.map((msg) => ({
              id: this.nextId++,
              from: msg.role,
              content: msg.content,
            }))
          );
          this.scrollToBottom();
        },
        error: () => {
          this.messages.set([]);
        },
      });
  }

  createTopic(): void {
    const name = this.newTopicName().trim();
    if (!name) {
      return;
    }

    this.http
      .post<TopicDetail>(`${environment.apiUrl}/topics/`, { name })
      .subscribe({
        next: (topic) => {
          this.newTopicName.set('');
          this.pendingTopicSelection = topic.id;
          this.selectTopic(topic.id, true);
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
          this.topics.update((entries) =>
            entries.map((entry) =>
              entry.id === topic.id
                ? {
                    id: topic.id,
                    name: topic.name,
                    message_count: topic.message_count,
                  }
                : entry
            )
          );
        },
      });
  }
}
