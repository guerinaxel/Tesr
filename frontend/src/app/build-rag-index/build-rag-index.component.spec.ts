import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { environment } from '../../environments/environment';
import { BuildRagIndexComponent } from './build-rag-index.component';

describe('BuildRagIndexComponent', () => {
  let fixture: ComponentFixture<BuildRagIndexComponent>;
  let component: BuildRagIndexComponent;
  let httpMock: HttpTestingController;

  const flushInitialRoot = (
    value: string | null = '/workspace/default',
    progress = { status: 'idle', percent: 0, message: 'waiting', root: null }
  ) => {
    const initReq = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    expect(initReq.request.method).toBe('GET');
    initReq.flush({ root: value, progress });
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BuildRagIndexComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();

    fixture = TestBed.createComponent(BuildRagIndexComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads the last used root on init', () => {
    // Arrange & Act handled in setup

    flushInitialRoot();

    // Assert
    expect(component.root).toBe('/workspace/default');
    expect(component.lastUsedRoot).toBe('/workspace/default');
  });

  it('sends the root value to the backend and shows a success toast', () => {
    // Arrange
    flushInitialRoot();
    component.root = '/workspace/project';

    // Act
    component.onSubmit();

    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    
    // Assert
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ root: '/workspace/project' });

    req.flush({ detail: 'ok', progress: { status: 'running', percent: 10, message: 'start', root: '/workspace/project' } });

    expect(component.toast).toEqual(
      jasmine.objectContaining({ type: 'success' })
    );
    expect(component.isSubmitting).toBeFalse();
    expect(component.lastUsedRoot).toBe('/workspace/project');
  });

  it('shows an error toast when the request fails', () => {
    // Arrange
    flushInitialRoot();
    component.root = '';

    // Act
    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    req.flush({ detail: 'Command failed' }, { status: 500, statusText: 'Error' });

    // Assert
    expect(component.toast).toEqual(
      jasmine.objectContaining({ type: 'error', message: 'Command failed' })
    );
    expect(component.isSubmitting).toBeFalse();
  });

  it('keeps the submit button in loading state until the call resolves', () => {
    // Arrange
    flushInitialRoot();
    component.root = '/tmp';

    // Act
    component.onSubmit();
    component.onSubmit();

    const requests = httpMock.match(`${environment.apiUrl}/code-qa/build-rag/`);
    
    // Assert
    expect(requests.length).toBe(1);
    expect(component.isSubmitting).toBeTrue();

    requests[0].flush({ detail: 'done', progress: { status: 'running', percent: 12, message: 'start', root: '/tmp' } });
    expect(component.isSubmitting).toBeFalse();
  });

  it('rebuilds using the last known root value', () => {
    // Arrange
    flushInitialRoot();
    component.lastUsedRoot = '/stored/root';

    // Act
    component.onRebuild();

    const request = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    
    // Assert
    expect(request.request.body).toEqual({ root: '/stored/root' });
    request.flush({ detail: 'ok', root: '/stored/root', progress: { status: 'running', percent: 20, message: 'start', root: '/stored/root' } });

    expect(component.root).toBe('/stored/root');
    expect(component.lastUsedRoot).toBe('/stored/root');
  });

  it('displays and refreshes build progress while running', fakeAsync(() => {
    // Arrange
    const runningProgress = { status: 'running', percent: 25, message: 'Collecting code', root: '/workspace/default' };
    flushInitialRoot('/workspace/default', runningProgress);

    // Act
    tick(component.pollIntervalMs);

    // Assert
    const poll = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    expect(poll.request.method).toBe('GET');
    poll.flush({ progress: { status: 'completed', percent: 100, message: 'done', root: '/workspace/default' } });

    expect(component.progress?.status).toBe('completed');
  }));
});
