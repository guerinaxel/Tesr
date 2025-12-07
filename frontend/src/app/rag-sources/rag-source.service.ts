import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { CodeQaResponse } from '../chat/chat-data.service';

export interface RagSource {
  id: string;
  name: string;
  description: string;
  path: string;
  created_at: string;
  total_files: number;
  total_chunks: number;
}

export interface BuildRagSourcePayload {
  name?: string | null;
  description?: string | null;
  paths: string[];
}

export interface UpdateRagSourcePayload {
  name?: string;
  description?: string;
}

export type RebuildRagSourcePayload = BuildRagSourcePayload;

@Injectable({ providedIn: 'root' })
export class RagSourceService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  getSources(): Observable<RagSource[]> {
    return this.http.get<RagSource[]>(`${this.apiUrl}/rag-sources/`);
  }

  buildSource(payload: BuildRagSourcePayload): Observable<RagSource> {
    return this.http.post<RagSource>(`${this.apiUrl}/rag-sources/build/`, payload);
  }

  updateSource(id: string, payload: UpdateRagSourcePayload): Observable<RagSource> {
    return this.http.patch<RagSource>(`${this.apiUrl}/rag-sources/${id}/`, payload);
  }

  rebuildSource(id: string, payload: RebuildRagSourcePayload): Observable<RagSource> {
    return this.http.post<RagSource>(`${this.apiUrl}/rag-sources/${id}/rebuild/`, payload);
  }

  queryRag(
    question: string,
    sources: string[],
    extra: Record<string, unknown> = {}
  ): Observable<CodeQaResponse> {
    const body = { question, sources, ...extra };
    return this.http.post<CodeQaResponse>(`${this.apiUrl}/code-qa/`, body);
  }
}
