import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../environments/environment';
import { CodeQaResponse } from '../chat/chat-data.service';
import { RagSourceService, BuildRagSourcePayload } from './rag-source.service';

describe('RagSourceService', () => {
  let service: RagSourceService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(RagSourceService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('fetches rag sources', () => {
    // Arrange
    const expectedUrl = `${environment.apiUrl}/rag-sources/`;

    // Act
    service.getSources().subscribe();

    // Assert
    const req = httpMock.expectOne(expectedUrl);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('builds a new source with provided payload', () => {
    // Arrange
    const payload: BuildRagSourcePayload = { name: 'Docs', description: 'Docs portal', paths: ['/tmp/docs'] };

    // Act
    service.buildSource(payload).subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/rag-sources/build/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(payload);
    req.flush({});
  });

  it('updates a rag source', () => {
    // Arrange
    const payload = { name: 'Backend v2', description: 'Updated' };

    // Act
    service.updateSource('source-1', payload).subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/rag-sources/source-1/`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual(payload);
    req.flush({});
  });

  it('rebuilds a rag source', () => {
    // Arrange
    const payload = { name: 'Backend', description: 'API', paths: ['/tmp/new'] };

    // Act
    service.rebuildSource('source-2', payload).subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/rag-sources/source-2/rebuild/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(payload);
    req.flush({});
  });

  it('queries the RAG endpoint with question, sources and extra options', () => {
    // Arrange
    const extra = { topic_id: 1, system_prompt: 'custom' };

    // Act
    service.queryRag('Hello?', ['source-1', 'source-2'], extra).subscribe((response: CodeQaResponse) => {
      expect(response).toEqual({ answer: 'Hi', sources_used: [] });
    });

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ question: 'Hello?', sources: ['source-1', 'source-2'], ...extra });
    req.flush({ answer: 'Hi', sources_used: [] });
  });
});
