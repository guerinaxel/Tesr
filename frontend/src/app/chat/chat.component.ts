import {
  CdkVirtualScrollViewport,
  ScrollingModule,
} from '@angular/cdk/scrolling';
import {
  Component,
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
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import {
  ChatDataService,
  CodeQaPayload,
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
    ScrollingModule,
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

  @ViewChild('topicsViewport') topicsViewport?: CdkVirtualScrollViewport;
  @ViewChild('messagesViewport') messagesViewport?: CdkVirtualScrollViewport;

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
  private topicsOffset = 0;
  private readonly topicsPageSize = 20;
  private hasMoreTopics = true;
  private topicsLoading = false;
  private messagesOffset = 0;
  private readonly messagesPageSize = 30;
  private hasMoreMessages = true;
  private messagesLoading = false;
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
  readonly topicSearchQuery = model('');
  readonly topicSearchResults = signal<TopicSummary[]>([]);
  readonly isTopicSearchVisible = signal(false);
  readonly topicSearchLoading = signal(false);

  private readonly topicSearch$ = new Subject<string>();

  ngOnInit(): void {
    this.loadTopics(this.initialTopicId(), true);

    if ((window as any).Cypress) {
      (window as any).chatComponent = this;
    }

    this.topicSearch$
      .pipe(debounceTime(500), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((term) => {
        const query = term.trim();
        if (!query) {
          this.topicSearchResults.set([]);
          this.topicSearchLoading.set(false);
          return;
        }

        this.topicSearchLoading.set(true);
        this.chatDataService.searchEverything(query, { limit: 5 }).subscribe({
          next: (res) => {
            this.topicSearchResults.set(res.topics.items ?? []);
            this.topicSearchLoading.set(false);
          },
          error: () => {
            this.topicSearchResults.set([]);
            this.topicSearchLoading.set(false);
          },
        });
      });
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
      payload.topic_id = this.selectedTopicId() ?? undefined;
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
    const viewport = this.messagesViewport;
    if (!viewport) return;
    setTimeout(() => {
      viewport.scrollToIndex(this.messages().length, 'smooth');
    }, 0);
  }

  private finishSending(): void {
    setTimeout(() => {
      this.isSending.set(false);
    }, 200);
  }

  loadTopics(selectTopicId: number | null = null, reset = false): void {
    if (this.topicsLoading || (!this.hasMoreTopics && !reset)) {
      return;
    }

    if (reset) {
      this.topics.set([]);
      this.topicsOffset = 0;
      this.hasMoreTopics = true;
    }

    this.topicsLoading = true;
    this.chatDataService
      .getTopics({ offset: this.topicsOffset, limit: this.topicsPageSize })
      .subscribe({
        next: (res) => {
          const existingIds = new Set(this.topics().map((entry) => entry.id));
          const newTopics = (res.topics ?? []).filter(
            (entry) => !existingIds.has(entry.id)
          );

          this.topics.update((entries) => [...entries, ...newTopics]);
          this.hasMoreTopics = Boolean(res.next_offset);
          this.topicsOffset = res.next_offset ?? this.topicsOffset + newTopics.length;

          if (!this.topics().length) {
            this.selectedTopicId.set(null);
            this.resetMessages();
            return;
          }

          const desiredTopicId = selectTopicId ?? this.selectedTopicId();
          const forceReload = selectTopicId != null;
          const chosenTopicId = desiredTopicId ?? this.topics()[0]?.id ?? null;

          if (chosenTopicId != null) {
            this.selectTopic(chosenTopicId, forceReload);
          }
        },
        error: () => {
          this.topics.set([]);
          this.selectedTopicId.set(null);
          this.messages.set([]);
          this.topicsLoading = false;
        },
        complete: () => {
          this.topicsLoading = false;
        },
      });
  }

  selectTopic(topicId: number, force = false): void {
    if (this.selectedTopicId() === topicId && !force) {
      return;
    }

    this.selectedTopicId.set(topicId);
    this.resetMessages();
    this.loadMessages(topicId, true);
  }

  createTopic(): void {
    const name = this.newTopicName().trim();
    if (!name) {
      return;
    }

    this.chatDataService.createTopic(name).subscribe({
      next: (topic) => {
        this.newTopicName.set('');
        this.selectTopic(topic.id, true);
        this.loadTopics(topic.id, true);
      },
    });
  }

  private refreshTopicMetadata(topicId: number | null): void {
    if (!topicId) return;

    this.chatDataService.getTopicDetail(topicId, { limit: 0 }).subscribe({
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

  onTopicsScrolled(index: number): void {
    if (index >= this.topics().length - 5) {
      this.loadTopics();
    }
  }

  onMessagesScrolled(index: number): void {
    if (index >= this.messages().length - 5) {
      const topicId = this.selectedTopicId();
      if (topicId != null) {
        this.loadMessages(topicId);
      }
    }
  }

  topicTrackBy = (_: number, topic: TopicSummary) => topic.id;
  messageTrackBy = (_: number, message: ChatMessage) => message.id;

  openTopicSearch(): void {
    this.isTopicSearchVisible.set(true);
    setTimeout(() => {
      const input = document.querySelector<HTMLInputElement>('#topic-search-input');
      input?.focus();
    });
  }

  closeTopicSearch(): void {
    this.isTopicSearchVisible.set(false);
    this.topicSearchQuery.set('');
    this.topicSearchResults.set([]);
  }

  onTopicSearchChange(value: string): void {
    this.topicSearchQuery.set(value);
    this.topicSearch$.next(value);
  }

  selectTopicFromSearch(topicId: number): void {
    this.selectTopic(topicId, true);
    this.closeTopicSearch();
  }

  private resetMessages(): void {
    this.messages.set([]);
    this.nextId = 1;
    this.messagesOffset = 0;
    this.hasMoreMessages = true;
  }

  private loadMessages(topicId: number, reset = false): void {
    if (this.messagesLoading || (!this.hasMoreMessages && !reset)) {
      return;
    }

    if (reset) {
      this.resetMessages();
    }

    this.messagesLoading = true;
    this.chatDataService
      .getTopicDetail(topicId, {
        offset: this.messagesOffset,
        limit: this.messagesPageSize,
      })
      .subscribe({
        next: (res) => {
          const incomingMessages: ChatMessage[] = (res.messages ?? []).map(
            (msg) => ({
              id: this.nextId++,
              from: msg.role,
              content: msg.content,
            })
          );

          this.messages.update((current) =>
            reset ? incomingMessages : [...current, ...incomingMessages]
          );
          this.hasMoreMessages = Boolean(res.next_offset);
          this.messagesOffset =
            res.next_offset ?? this.messagesOffset + incomingMessages.length;
          this.scrollToBottom();
        },
        error: () => {
          if (reset) {
            this.messages.set([]);
          }
          this.messagesLoading = false;
        },
        complete: () => {
          this.messagesLoading = false;
        },
      });
  }
}
