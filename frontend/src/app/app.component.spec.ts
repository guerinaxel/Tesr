import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { RouterTestingModule } from '@angular/router/testing';

import { AppComponent } from './app.component';
import { ChatDataService, SearchResponse } from './chat/chat-data.service';

const baseResponse: SearchResponse = {
  topics: { items: [{ id: 1, name: 'Topic', message_count: 1 }], next_offset: null },
  questions: { items: [{ id: 5, topic_id: 1, topic_name: 'Topic', content: 'Why?' }], next_offset: null },
  answers: { items: [{ id: 9, topic_id: 1, topic_name: 'Topic', content: 'Because' }], next_offset: null },
};

describe('AppComponent', () => {
  let fixture: ComponentFixture<AppComponent>;
  let component: AppComponent;
  let chatDataService: jasmine.SpyObj<ChatDataService>;

  beforeEach(async () => {
    chatDataService = jasmine.createSpyObj<ChatDataService>('ChatDataService', [
      'searchEverything',
    ]);

    await TestBed.configureTestingModule({
      imports: [AppComponent, RouterTestingModule],
      providers: [{ provide: ChatDataService, useValue: chatDataService }],
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    component = fixture.componentInstance;
    TestBed.runInInjectionContext(() => component.ngOnInit());
  });

  afterEach(() => {
    delete (window as any).appComponent;
    delete (window as any).Cypress;
  });

  it('debounces global search input and updates results', fakeAsync(() => {
    // Arrange
    chatDataService.searchEverything.and.returnValue(of(baseResponse));

    // Act
    component.onGlobalSearchChange('  hello ');

    tick(499);
    const firstCallCount = chatDataService.searchEverything.calls.count();

    // Assert
    expect(firstCallCount).toBe(0);

    tick(1);

    expect(chatDataService.searchEverything).toHaveBeenCalledWith('hello', {
      limit: 5,
      topics_offset: 0,
      questions_offset: 0,
      answers_offset: 0,
    });
    expect(component.globalSearchLoading()).toBeFalse();
    expect(component.globalSearchResults()).toEqual(baseResponse);
    expect(component.hasSearchResults()).toBeTrue();
  }));

  it('clears search state and hides the dropdown', () => {
    // Arrange
    component.globalSearchQuery.set('query');
    component.globalSearchResults.set(baseResponse);
    component.searchVisible.set(true);

    // Act
    component.clearGlobalSearch();

    // Assert
    expect(component.globalSearchQuery()).toBe('');
    expect(component.globalSearchResults()).toBeNull();
    expect(component.searchVisible()).toBeFalse();
    expect(component.searchOffsets()).toEqual({ topics: 0, questions: 0, answers: 0 });
  });

  it('does not search when the query is empty after trimming', fakeAsync(() => {
    // Arrange
    component.onGlobalSearchChange('   ');

    // Act
    tick(600);

    // Assert
    expect(chatDataService.searchEverything).not.toHaveBeenCalled();
    expect(component.globalSearchResults()).toBeNull();
    expect(component.globalSearchLoading()).toBeFalse();
  }));

  it('reports no results when the search payload is empty', () => {
    // Arrange
    expect(component.hasSearchResults()).toBeFalse();

    // Act
    component.globalSearchResults.set({
      topics: { items: [], next_offset: null },
      questions: { items: [], next_offset: null },
      answers: { items: [], next_offset: null },
    });

    // Assert
    expect(component.hasSearchResults()).toBeFalse();
  });

  it('detects search results when only questions exist', () => {
    component.globalSearchResults.set({
      topics: { items: [], next_offset: null },
      questions: { items: [{ id: 2, topic_id: 1, topic_name: 'Only', content: 'Q' }], next_offset: null },
      answers: { items: [], next_offset: null },
    });

    expect(component.hasSearchResults()).toBeTrue();
  });

  it('detects search results when only answers exist', () => {
    component.globalSearchResults.set({
      topics: { items: [], next_offset: null },
      questions: { items: [], next_offset: null },
      answers: { items: [{ id: 3, topic_id: 1, topic_name: 'Only', content: 'A' }], next_offset: null },
    });

    expect(component.hasSearchResults()).toBeTrue();
  });

  it('loads more results for a category using the stored offsets', () => {
    // Arrange
    chatDataService.searchEverything.and.returnValue(of(baseResponse));

    component.globalSearchQuery.set('topic');
    component.globalSearchResults.set({
      ...baseResponse,
      topics: { ...baseResponse.topics, next_offset: 10 },
    });

    // Act
    component.loadMore('topics');

    // Assert
    expect(chatDataService.searchEverything).toHaveBeenCalledWith('topic', {
      limit: 5,
      topics_offset: 10,
      questions_offset: 0,
      answers_offset: 0,
    });
    expect(component.searchOffsets().topics).toBe(10);
  });

  it('ignores load more when no next offset exists', () => {
    // Arrange
    chatDataService.searchEverything.and.returnValue(of(baseResponse));
    component.globalSearchQuery.set('topic');
    component.globalSearchResults.set({ ...baseResponse, topics: { items: [], next_offset: null } });

    // Act
    component.loadMore('topics');

    // Assert
    expect(chatDataService.searchEverything).not.toHaveBeenCalled();
  });

  it('resets results and loading state when a search fails', fakeAsync(() => {
    // Arrange
    chatDataService.searchEverything.and.returnValue(
      throwError(() => new Error('search failed'))
    );

    // Act
    component.onGlobalSearchChange('fail');
    tick(500);

    // Assert
    expect(component.globalSearchResults()).toBeNull();
    expect(component.globalSearchLoading()).toBeFalse();
  }));

  it('exposes the component on window when Cypress is present', () => {
    // Arrange
    (window as any).Cypress = true;

    const cypressFixture = TestBed.createComponent(AppComponent);
    const cypressComponent = cypressFixture.componentInstance;
    TestBed.runInInjectionContext(() => cypressComponent.ngOnInit());

    // Assert
    expect((window as any).appComponent).toBe(cypressComponent);
  });
});
