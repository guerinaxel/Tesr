import {
  CdkVirtualScrollViewport,
  ScrollingModule,
} from '@angular/cdk/scrolling';
import {
  Component,
  DestroyRef,
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
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import {
  ChatDataService,
  CodeQaPayload,
  TopicSummary,
} from './chat-data.service';
import { RagSource, RagSourceService } from '../rag-sources/rag-source.service';

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
    MatDividerModule,
  ],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent implements OnInit {
  private readonly chatDataService = inject(ChatDataService);
  private readonly ragSourceService = inject(RagSourceService);
  private readonly destroyRef = inject(DestroyRef);

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
  readonly ragSources = signal<RagSource[]>([]);
  readonly selectedSources = signal<string[]>([]);
  readonly ragSourcesLoading = signal(false);
  readonly ragSourceError = signal('');
  readonly buildSourceName = model('');
  readonly buildSourceDescription = model('');
  readonly buildSourcePaths = model('');
  readonly isBuildFormOpen = signal(false);
  readonly editingSourceId = signal<string | null>(null);
  readonly editSourceName = model('');
  readonly editSourceDescription = model('');
  readonly editSourceError = signal('');
  readonly rebuildingSourceId = signal<string | null>(null);
  readonly rebuildSourceName = model('');
  readonly rebuildSourceDescription = model('');
  readonly rebuildSourcePaths = model('');
  readonly rebuildSourceError = signal('');
  readonly lastSourcesUsed = signal<string[]>([]);
  private topicsOffset = 0;
  private readonly topicsPageSize = 20;
  private hasMoreTopics = true;
  private topicsLoading = false;
  private messagesOffset = 0;
  private readonly messagesPageSize = 30;
  private hasMoreMessages = true;
  private messagesLoading = false;
  private nextId = 1;
  private streamSub: Subscription | null = null;
  private streamingMessageId: number | null = null;
  private shouldStickToBottom = true;

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
  readonly hasRagSources = computed(() => this.ragSources().length > 0);
  readonly sourcesLabel = computed(() =>
    this.selectedSources().length
      ? `${this.selectedSources().length} source(s) sélectionnée(s)`
      : 'Aucune source sélectionnée'
  );

  private readonly topicSearch$ = new Subject<string>();

  ngOnInit(): void {
    this.loadTopics(this.initialTopicId(), true);
    this.loadRagSources();

    if ((window as any).Cypress) {
      (window as any).chatComponent = this;
    }

    this.topicSearch$
      .pipe(
        debounceTime(500),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
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

    this.destroyRef.onDestroy(() => this.stopStreaming());
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

    if (!this.selectedSources().length) {
        this.messages.update((msgs) => [
          ...msgs,
          {
            id: this.nextId++,
            from: 'assistant',
            content: 'Sélectionnez au moins une source RAG avant de poser une question.',
            isError: true,
          },
        ]);
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
    this.lastSourcesUsed.set([]);
    this.scrollToBottom(true);

    const payload: CodeQaPayload = {
      question: text,
      system_prompt: this.systemPrompt(),
      sources: this.selectedSources(),
    };

    if (this.isCustomPrompt()) {
      payload.custom_prompt = this.customPrompt().trim();
    }

    const sendWithTopic = (topicId: number | null) => {
      if (topicId) {
        payload.topic_id = topicId;
      }
      this.startStreamingAnswer(payload);
    };

    this.ensureTopicSelection(text, sendWithTopic);
  }

  onEnterSend(event: KeyboardEvent): void {
    if (event.shiftKey) {
      return;
    }

    event.preventDefault();
    this.onSubmit();
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

  private scrollToBottom(force = false): void {
    const viewport = this.messagesViewport;
    /* istanbul ignore next */
    if (!viewport) return;
    /* istanbul ignore next */
    if (!force && !this.shouldStickToBottom) return;
    setTimeout(() => {
      viewport.scrollToIndex(this.messages().length, 'smooth');
    }, 0);
  }

  private ensureTopicSelection(questionText: string, onReady: (topicId: number | null) => void) {
    const existingTopicId = this.selectedTopicId();
    if (existingTopicId != null) {
      onReady(existingTopicId);
      return;
    }

    const topicName = this.buildTopicName(questionText);

    this.chatDataService.createTopic(topicName).subscribe({
      next: (topic) => {
        const summary: TopicSummary = {
          id: topic.id,
          name: topic.name,
          message_count: topic.message_count,
        };

        this.selectedTopicId.set(topic.id);
        this.topics.update((entries) => {
          const existing = entries.find((entry) => entry.id === topic.id);
          if (existing) {
            return entries.map((entry) =>
              entry.id === topic.id ? summary : entry
            );
          }

          return [summary, ...entries];
        });
        this.hasMoreMessages = false;
        onReady(topic.id);
      },
      error: (err) => {
        const detail =
          err?.message ?? err?.toString?.() ?? 'Erreur lors de la création du topic.';
        this.messages.update((msgs) => [
          ...msgs,
          { id: this.nextId++, from: 'assistant', content: detail, isError: true },
        ]);
        this.finishSending();
      },
    });
  }

  private buildTopicName(questionText: string): string {
    const normalized = questionText.trim().replace(/\s+/g, ' ');
    const maxLength = 60;
    if (!normalized) {
      return 'Nouvelle conversation';
    }

    if (normalized.length <= maxLength) {
      return normalized;
    }

    return normalized.slice(0, maxLength - 1) + '…';
  }

  private finishSending(): void {
    setTimeout(() => {
      this.isSending.set(false);
    }, 200);
  }

  private stopStreaming(): void {
    if (this.streamSub) {
      this.streamSub.unsubscribe();
      this.streamSub = null;
      this.streamingMessageId = null;
    }
  }

  private startStreamingAnswer(payload: CodeQaPayload): void {
    this.stopStreaming();
    const assistantMsg: ChatMessage = {
      id: this.nextId++,
      from: 'assistant',
      content: '',
    };
    this.streamingMessageId = assistantMsg.id;
    this.messages.update((msgs) => [...msgs, assistantMsg]);

    this.streamSub = this.chatDataService.streamQuestion(payload).subscribe({
      next: (chunk) => {
        if (!chunk || typeof chunk !== 'object') return;
        const event = (chunk as any).event;
        const data = (chunk as any).data;

        if (event === 'meta' && data) {
          const meta = data as any;
          const names: string[] = Array.isArray(meta.source_names)
            ? meta.source_names
            : Array.isArray(meta.contexts)
              ? Array.from(
                  new Set(
                    (meta.contexts as Array<{ source_name?: string }>).
                      map((ctx) => ctx.source_name || '').filter(Boolean)
                  )
                )
              : [];
          this.lastSourcesUsed.set(names);
        }

        if (event === 'token' && typeof data === 'string') {
          this.messages.update((msgs) =>
            msgs.map((msg) =>
              msg.id === this.streamingMessageId
                ? { ...msg, content: msg.content + data }
                : msg
            )
          );
          this.scrollToBottom();
          return;
        }

        if (event === 'error' && typeof data === 'string') {
          this.messages.update((msgs) =>
            msgs.map((msg) =>
              msg.id === this.streamingMessageId
                ? { ...msg, content: data, isError: true }
                : msg
            )
          );
          this.finishSending();
          this.stopStreaming();
          return;
        }

        if (event === 'done') {
          const answer = typeof data === 'object' && data ? (data as any).answer ?? '' : '';
          if (answer) {
            this.messages.update((msgs) =>
              msgs.map((msg) =>
                msg.id === this.streamingMessageId
                  ? { ...msg, content: answer as string }
                  : msg
              )
            );
          }

          this.finishSending();
          this.refreshTopicMetadata(this.selectedTopicId());
          this.stopStreaming();
          this.scrollToBottom();
        }
      },
      error: (err) => {
        const detail =
          err?.message ?? err?.toString?.() ?? 'Erreur lors de la requête à /api/code-qa/stream/.';
        this.messages.update((msgs) => [
          ...msgs,
          { id: this.nextId++, from: 'assistant', content: detail, isError: true },
        ]);
        this.finishSending();
        this.stopStreaming();
        this.scrollToBottom(true);
      },
    });
  }

  loadRagSources(): void {
    this.ragSourcesLoading.set(true);
    this.ragSourceService.getSources().subscribe({
      next: (sources) => {
        this.ragSources.set(sources);
        if (!this.selectedSources().length && sources.length) {
          this.selectedSources.set(sources.map((src) => src.id));
        }
      },
      error: () => {
        this.ragSources.set([]);
        this.ragSourcesLoading.set(false);
      },
      complete: () => this.ragSourcesLoading.set(false),
    });
  }

  toggleBuildForm(): void {
    this.isBuildFormOpen.update((current) => !current);
    this.ragSourceError.set('');
  }

  buildNewSource(): void {
    const rawPaths = this.buildSourcePaths()
      .split(/\n|,/)
      .map((entry) => entry.trim())
      .filter(Boolean);

    if (!rawPaths.length) {
      this.ragSourceError.set('Ajoutez au moins un chemin de dossier.');
      return;
    }

    const payload = {
      name: this.buildSourceName().trim() || null,
      description: this.buildSourceDescription().trim() || null,
      paths: rawPaths,
    };

    this.ragSourceError.set('');
    this.ragSourcesLoading.set(true);

    this.ragSourceService.buildSource(payload).subscribe({
      next: (source) => {
        this.ragSources.update((sources) => [source, ...sources]);
        this.selectedSources.update((current) => [...new Set([...current, source.id])]);
        this.buildSourceName.set('');
        this.buildSourceDescription.set('');
        this.buildSourcePaths.set('');
        this.isBuildFormOpen.set(false);
      },
      error: (err) => {
        const detail =
          err?.error?.detail ??
          err?.message ??
          'Impossible de créer la source RAG. Vérifiez les chemins fournis.';
        this.ragSourceError.set(detail);
        this.ragSourcesLoading.set(false);
      },
      complete: () => this.ragSourcesLoading.set(false),
    });
  }

  startEditSource(source: RagSource): void {
    this.editingSourceId.set(source.id);
    this.editSourceName.set(source.name);
    this.editSourceDescription.set(source.description);
    this.editSourceError.set('');
    this.rebuildingSourceId.set(null);
  }

  cancelEditSource(): void {
    this.editingSourceId.set(null);
    this.editSourceName.set('');
    this.editSourceDescription.set('');
    this.editSourceError.set('');
  }

  saveSourceEdits(): void {
    const sourceId = this.editingSourceId();
    if (!sourceId) {
      return;
    }

    const name = this.editSourceName().trim();
    const description = this.editSourceDescription().trim();

    if (!name) {
      this.editSourceError.set('Le nom est requis.');
      return;
    }

    this.ragSourcesLoading.set(true);
    this.ragSourceService.updateSource(sourceId, { name, description }).subscribe({
      next: (updated) => {
        this.ragSources.update((sources) =>
          sources.map((source) => (source.id === updated.id ? updated : source))
        );
        this.selectedSources.update((current) =>
          current.includes(updated.id) ? current : [...current, updated.id]
        );
        this.cancelEditSource();
      },
      error: (err) => {
        const detail =
          err?.error?.detail ?? err?.message ?? 'Impossible de mettre à jour la source.';
        this.editSourceError.set(detail);
      },
      complete: () => this.ragSourcesLoading.set(false),
    });
  }

  startRebuildSource(source: RagSource): void {
    this.rebuildingSourceId.set(source.id);
    this.rebuildSourceName.set(source.name);
    this.rebuildSourceDescription.set(source.description);
    this.rebuildSourcePaths.set('');
    this.rebuildSourceError.set('');
    this.editingSourceId.set(null);
  }

  cancelRebuildSource(): void {
    this.rebuildingSourceId.set(null);
    this.rebuildSourceName.set('');
    this.rebuildSourceDescription.set('');
    this.rebuildSourcePaths.set('');
    this.rebuildSourceError.set('');
  }

  rebuildSource(): void {
    const sourceId = this.rebuildingSourceId();
    if (!sourceId) {
      return;
    }

    const rawPaths = this.rebuildSourcePaths()
      .split(/\n|,/)
      .map((entry) => entry.trim())
      .filter(Boolean);

    if (!rawPaths.length) {
      this.rebuildSourceError.set('Ajoutez au moins un chemin de dossier.');
      return;
    }

    const payload = {
      name: this.rebuildSourceName().trim() || null,
      description: this.rebuildSourceDescription().trim() || null,
      paths: rawPaths,
    };

    this.ragSourcesLoading.set(true);
    this.ragSourceService.rebuildSource(sourceId, payload).subscribe({
      next: (updated) => {
        this.ragSources.update((sources) =>
          sources.map((source) => (source.id === updated.id ? updated : source))
        );
        this.selectedSources.update((current) =>
          current.includes(updated.id) ? current : [...current, updated.id]
        );
        this.cancelRebuildSource();
      },
      error: (err) => {
        const detail =
          err?.error?.detail ?? err?.message ?? 'Impossible de reconstruire la source.';
        this.rebuildSourceError.set(detail);
      },
      complete: () => this.ragSourcesLoading.set(false),
    });
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

    this.updateAutoScrollState();
  }

  private updateAutoScrollState(): void {
    const viewport = this.messagesViewport;
    if (!viewport) {
      this.shouldStickToBottom = true;
      return;
    }

    this.shouldStickToBottom = viewport.measureScrollOffset('bottom') < 32;
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
    this.shouldStickToBottom = true;
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
          this.scrollToBottom(true);
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
