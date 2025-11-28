import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { environment } from '../../environments/environment';
import { BuildRagIndexComponent } from './build-rag-index.component';

describe('BuildRagIndexComponent', () => {
  let fixture: ComponentFixture<BuildRagIndexComponent>;
  let component: BuildRagIndexComponent;
  let httpMock: HttpTestingController;

  const flushInitialRoot = (value: string | null = '/workspace/default') => {
    const initReq = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    expect(initReq.request.method).toBe('GET');
    initReq.flush({ root: value });
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BuildRagIndexComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();

    fixture = TestBed.createComponent(BuildRagIndexComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    flushInitialRoot();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads the last used root on init', () => {
    expect(component.root).toBe('/workspace/default');
    expect(component.lastUsedRoot).toBe('/workspace/default');
  });

  it('sends the root value to the backend and shows a success toast', () => {
    component.root = '/workspace/project';

    component.onSubmit();

    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ root: '/workspace/project' });

    req.flush({ detail: 'ok' });

    expect(component.toast).toEqual(
      jasmine.objectContaining({ type: 'success' })
    );
    expect(component.isSubmitting).toBeFalse();
    expect(component.lastUsedRoot).toBe('/workspace/project');
  });

  it('shows an error toast when the request fails', () => {
    component.root = '';

    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    req.flush({ detail: 'Command failed' }, { status: 500, statusText: 'Error' });

    expect(component.toast).toEqual(
      jasmine.objectContaining({ type: 'error', message: 'Command failed' })
    );
    expect(component.isSubmitting).toBeFalse();
  });

  it('keeps the submit button in loading state until the call resolves', () => {
    component.root = '/tmp';

    component.onSubmit();
    component.onSubmit();

    const requests = httpMock.match(`${environment.apiUrl}/code-qa/build-rag/`);
    expect(requests.length).toBe(1);
    expect(component.isSubmitting).toBeTrue();

    requests[0].flush({ detail: 'done' });
    expect(component.isSubmitting).toBeFalse();
  });

  it('rebuilds using the last known root value', () => {
    component.lastUsedRoot = '/stored/root';
    component.onRebuild();

    const request = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    expect(request.request.body).toEqual({ root: '/stored/root' });
    request.flush({ detail: 'ok', root: '/stored/root' });

    expect(component.root).toBe('/stored/root');
    expect(component.lastUsedRoot).toBe('/stored/root');
  });
});
