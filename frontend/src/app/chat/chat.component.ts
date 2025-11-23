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

import {
  ChatDataService,
  CodeQaPayload,
  TopicDetail,
  TopicSummary,
} from './chat-data.service';

interface ChatMessage {
  id: number;
  from: 'user' | 'assistant';
  content: string;
  isError?: boolean;
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
  private readonly chatDataService = inject(ChatDataService);

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
  readonly isRebuilding = signal(false);
  readonly topics = signal<TopicSummary[]>([]);
  readonly selectedTopicId = signal<number | null>(null);
  readonly newTopicName = model('');
  readonly rebuildRoot = model('');
  readonly rebuildFeedback = signal<string | null>(null);
  readonly rebuildHasError = signal(false);
  private pendingTopicSelection: number | null = null;
  private nextId = 1;
  private lastUsedRoot: string | null = null;
  private readonly rebuildRootStorageKey = 'chat.rebuildRoot';

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
    this.restoreRebuildRoot();
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

    const payload: CodeQaPayload = {
      question: text,
      system_prompt: this.systemPrompt(),
    };

    if (this.selectedTopicId()) {
      payload.topic_id = String(this.selectedTopicId());
    }

    if (this.isCustomPrompt()) {
      payload.custom_prompt = this.customPrompt().trim();
    }

    this.chatDataService.sendQuestion(payload).subscribe({
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
    this.chatDataService.getTopics().subscribe({
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
    this.chatDataService.getTopicDetail(topicId).subscribe({
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

    this.chatDataService.createTopic(name).subscribe({
      next: (topic) => {
        this.newTopicName.set('');
        this.pendingTopicSelection = topic.id;
        this.selectTopic(topic.id, true);
        this.loadTopics(topic.id);
      },
    });
  }

  rebuildIndex(): void {
    if (this.isRebuilding()) return;

    this.isRebuilding.set(true);
    this.rebuildFeedback.set(null);
    this.rebuildHasError.set(false);

    const root = this.resolveRebuildRoot();

    this.chatDataService.rebuildIndex(root ?? undefined).subscribe({
      next: () => {
        if (root) {
          this.persistRebuildRoot(root);
        }

        this.rebuildHasError.set(false);
        this.rebuildFeedback.set('Index reconstruit avec succès.');
        this.isRebuilding.set(false);
      },
      error: (err) => {
        this.rebuildHasError.set(true);
        this.rebuildFeedback.set(
          err?.error?.detail ?? 'Erreur lors de la reconstruction de l\'index.'
        );
        this.isRebuilding.set(false);
      },
    });
  }

  private resolveRebuildRoot(): string | null {
    const topicRoot = this.selectedTopicId();
    if (topicRoot != null) {
      return String(topicRoot);
    }

    const typedRoot = this.rebuildRoot().trim();
    if (typedRoot) {
      return typedRoot;
    }

    return this.lastUsedRoot;
  }

  private restoreRebuildRoot(): void {
    const savedRoot = localStorage.getItem(this.rebuildRootStorageKey);
    if (!savedRoot) return;

    this.lastUsedRoot = savedRoot;
    this.rebuildRoot.set(savedRoot);
  }

  private persistRebuildRoot(root: string): void {
    this.lastUsedRoot = root;
    this.rebuildRoot.set(root);
    localStorage.setItem(this.rebuildRootStorageKey, root);
  }

  private refreshTopicMetadata(topicId: number | null): void {
    if (!topicId) return;

    this.chatDataService.getTopicDetail(topicId).subscribe({
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
