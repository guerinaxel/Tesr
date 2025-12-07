export const apiUrl = 'http://localhost:8000/api';

type Topic = {
  id: number;
  name: string;
  message_count: number;
  messages?: Array<{ role: 'user' | 'assistant'; content: string }>;
  next_offset?: number | null;
};

type ChatRequestBody = {
  question: string;
  system_prompt: string;
  custom_prompt?: string;
  topic_id?: number;
};

export const stubTopicList = (
  topics: Topic[],
  alias = 'listTopics',
  next_offset: number | null = null
) => {
  cy.intercept('GET', `${apiUrl}/topics/**`, (req) => {
    req.reply({ topics, next_offset });
  }).as(alias);
};

export const stubTopicDetail = (topic: Topic, alias = 'topicDetail') => {
  cy.intercept('GET', `${apiUrl}/topics/${topic.id}/**`, (req) => {
    req.reply({ ...topic, next_offset: topic.next_offset ?? null });
  }).as(alias);
};

export const stubCreateTopic = (topic: Topic, alias = 'createTopic') => {
  cy.intercept('POST', `${apiUrl}/topics/`, { ...topic, next_offset: topic.next_offset ?? null }).as(alias);
};

export const stubSendQuestion = (
  expectedBody: ChatRequestBody,
  responseBody: { answer: string },
  alias = 'sendQuestion'
) => {
  cy.intercept('POST', `${apiUrl}/code-qa/`, (req) => {
    expect(req.body).to.deep.equal(expectedBody);

    req.reply({
      statusCode: 200,
      body: responseBody,
    });
  }).as(alias);
};

export const stubStreamQuestion = (
  expectedBody: ChatRequestBody,
  events: Array<{ event: string; data: unknown }>,
  alias = 'streamQuestion'
) => {
  cy.intercept('POST', `${apiUrl}/code-qa/stream/`, (req) => {
    expect(req.body).to.deep.equal(expectedBody);
    const body = events.map((evt) => `data: ${JSON.stringify(evt)}\n\n`).join('');
    req.reply({
      statusCode: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body,
    });
  }).as(alias);
};

export const stubBuildRag = (alias = 'buildRag', progress = { status: 'running', percent: 10, message: 'Starting', root: '' }) => {
  cy.intercept('POST', `${apiUrl}/code-qa/build-rag/`, (req) => {
    req.reply({ statusCode: 200, body: { progress } });
  }).as(alias);
};

export const stubLastRagRoot = (
  root: string,
  alias = 'lastRagRoot',
  progress = { status: 'idle', percent: 0, message: 'En attente', root: null }
) => {
  cy.intercept('GET', `${apiUrl}/code-qa/build-rag/`, { root, progress }).as(alias);
};

export const stubSearch = (
  query: Record<string, string | undefined>,
  responseBody: unknown,
  alias = 'search'
) => {
  cy.intercept('GET', '**/search/**', (req) => {
    req.reply({ statusCode: 200, body: responseBody });
  }).as(alias);
};
