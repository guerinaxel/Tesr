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
    // Arrange & Act handled in setup

    // Assert
    expect(component.root).toBe('/workspace/default');
    expect(component.lastUsedRoot).toBe('/workspace/default');
  });

  it('sends the root value to the backend and shows a success toast', () => {
    // Arrange
    component.root = '/workspace/project';

    // Act
    component.onSubmit();

    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    
    // Assert
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
    // Arrange
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
    component.root = '/tmp';

    // Act
    component.onSubmit();
    component.onSubmit();

    const requests = httpMock.match(`${environment.apiUrl}/code-qa/build-rag/`);
    
    // Assert
    expect(requests.length).toBe(1);
    expect(component.isSubmitting).toBeTrue();

    requests[0].flush({ detail: 'done' });
    expect(component.isSubmitting).toBeFalse();
  });

  it('rebuilds using the last known root value', () => {
    // Arrange
    component.lastUsedRoot = '/stored/root';

    // Act
    component.onRebuild();

    const request = httpMock.expectOne(`${environment.apiUrl}/code-qa/build-rag/`);
    
    // Assert
    expect(request.request.body).toEqual({ root: '/stored/root' });
    request.flush({ detail: 'ok', root: '/stored/root' });

    expect(component.root).toBe('/stored/root');
    expect(component.lastUsedRoot).toBe('/stored/root');
  });
});
