import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export interface TopicSummary {
  id: number;
  name: string;
  message_count: number;
}

export interface TopicDetail extends TopicSummary {
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
  next_offset: number | null;
}

export interface PaginatedTopicList {
  topics: TopicSummary[];
  next_offset: number | null;
}

export interface SearchCategory<T> {
  items: T[];
  next_offset: number | null;
}

export type SearchTopicResult = TopicSummary;

export interface SearchMessageResult {
  id: number;
  topic_id: number;
  topic_name: string;
  content: string;
}

export interface SearchResponse {
  topics: SearchCategory<SearchTopicResult>;
  questions: SearchCategory<SearchMessageResult>;
  answers: SearchCategory<SearchMessageResult>;
}

export interface CodeQaPayload extends Record<string, string | number | undefined> {
  question: string;
  system_prompt: string;
  topic_id?: number;
  custom_prompt?: string;
}

export interface CodeQaResponse {
  answer: string;
  meta?: unknown;
}

export interface StreamChunk {
  event: 'meta' | 'token' | 'done' | 'error';
  data: unknown;
}

export interface PaginationOptions {
  offset?: number;
  limit?: number;
}

@Injectable({ providedIn: 'root' })
export class ChatDataService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  sendQuestion(payload: CodeQaPayload) {
    return this.http.post<CodeQaResponse>(`${this.apiUrl}/code-qa/`, payload);
  }

  streamQuestion(payload: CodeQaPayload): Observable<StreamChunk> {
    return new Observable<StreamChunk>((observer) => {
      const controller = new AbortController();
      let active = true;

      fetch(`${this.apiUrl}/code-qa/stream/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })
        .then((response) => {
          const reader = response.body?.getReader();
          if (!reader) {
            active = false;
            observer.error('Streaming not supported by the server response.');
            return;
          }

          const decoder = new TextDecoder();
          let buffer = '';

          const readChunk = (): void => {
            if (!active) {
              return;
            }

            reader
              .read()
              .then(({ done, value }) => {
                if (!active) {
                  return;
                }

                if (done) {
                  active = false;
                  observer.complete();
                  return;
                }

                buffer += decoder.decode(value, { stream: true });

                let delimiterIndex = buffer.indexOf('\n\n');
                while (delimiterIndex >= 0) {
                  const rawEvent = buffer.slice(0, delimiterIndex).trim();
                  buffer = buffer.slice(delimiterIndex + 2);

                  if (rawEvent.startsWith('data:')) {
                    const payloadText = rawEvent.slice(5).trim();
                    if (payloadText) {
                      try {
                        observer.next(JSON.parse(payloadText));
                      } catch (error) {
                        active = false;
                        observer.error(error);
                        controller.abort();
                        return;
                      }
                    }
                  }

                  delimiterIndex = buffer.indexOf('\n\n');
                }

                readChunk();
              })
              .catch((err) => {
                if (!active) return;
                active = false;
                observer.error(err);
              });
          };

          readChunk();
        })
        .catch((error) => {
          if (!active) return;
          active = false;
          observer.error(error);
        });

      return () => {
        active = false;
        controller.abort();
      };
    });
  }

  getTopics(options: PaginationOptions = {}) {
    const params = new HttpParams({ fromObject: this.buildPaginationParams(options) });

    return this.http.get<PaginatedTopicList>(`${this.apiUrl}/topics/`, { params });
  }

  getTopicDetail(topicId: number, options: PaginationOptions = {}) {
    const params = new HttpParams({ fromObject: this.buildPaginationParams(options) });

    return this.http.get<TopicDetail>(`${this.apiUrl}/topics/${topicId}/`, { params });
  }

  createTopic(name: string) {
    return this.http.post<TopicDetail>(`${this.apiUrl}/topics/`, { name });
  }

  searchEverything(query: string, options: Record<string, number> = {}) {
    let params = new HttpParams().set('q', query);

    const maybeAppend = (key: string, value: number | undefined) => {
      if (value != null) {
        params = params.set(key, String(value));
      }
    };

    maybeAppend('limit', options.limit);
    maybeAppend('topics_offset', options.topics_offset);
    maybeAppend('questions_offset', options.questions_offset);
    maybeAppend('answers_offset', options.answers_offset);

    return this.http.get<SearchResponse>(`${this.apiUrl}/search/`, { params });
  }

  private buildPaginationParams(options: PaginationOptions): Record<string, string> {
    const params: Record<string, string> = {};
    if (options.offset != null) {
      params['offset'] = String(options.offset);
    }
    if (options.limit != null) {
      params['limit'] = String(options.limit);
    }
    return params;
  }
}
