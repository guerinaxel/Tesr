import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { environment } from '../../environments/environment';
import { BuildRagIndexComponent } from './build-rag-index.component';

describe('BuildRagIndexComponent', () => {
  let fixture: ComponentFixture<BuildRagIndexComponent>;
  let component: BuildRagIndexComponent;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BuildRagIndexComponent, HttpClientTestingModule],
    }).compileComponents();

    fixture = TestBed.createComponent(BuildRagIndexComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
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
});
