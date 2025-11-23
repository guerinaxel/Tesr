export const apiUrl = 'http://localhost:8000/api';

type Topic = {
  id: number;
  name: string;
  message_count: number;
  messages?: Array<{ role: 'user' | 'assistant'; content: string }>;
};

type ChatRequestBody = {
  question: string;
  system_prompt: string;
  custom_prompt?: string;
  topic_id: string;
};

export const stubTopicList = (topics: Topic[], alias = 'listTopics') => {
  cy.intercept('GET', `${apiUrl}/topics/`, { topics }).as(alias);
};

export const stubTopicDetail = (topic: Topic, alias = 'topicDetail') => {
  cy.intercept('GET', `${apiUrl}/topics/${topic.id}/`, topic).as(alias);
};

export const stubCreateTopic = (topic: Topic, alias = 'createTopic') => {
  cy.intercept('POST', `${apiUrl}/topics/`, topic).as(alias);
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

export const stubBuildRag = (alias = 'buildRag') => {
  cy.intercept('POST', `${apiUrl}/code-qa/build-rag/`, (req) => {
    req.reply({ statusCode: 200, body: {} });
  }).as(alias);
};
