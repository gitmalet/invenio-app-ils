import React, { Component } from 'react';
import { Link } from 'react-router-dom';
import {
  Button,
  Card,
  Container,
  Grid,
  Segment,
  Icon,
  Header,
  Responsive,
  Accordion,
  Menu,
  Message,
} from 'semantic-ui-react';
import {
  ReactSearchKit,
  SearchBar,
  ResultsList,
  ResultsGrid,
  ResultsLoader,
  EmptyResults,
  Error,
  Pagination,
  Count,
  Aggregator,
  InvenioSearchApi,
} from 'react-searchkit';
import { getSearchConfig } from '../../../../common/config';
import { FrontSiteRoutes } from '../../../../routes/urls';
import {
  Error as IlsError,
  SearchBar as DocumentsSearchBar,
  ResultsSort,
} from '../../../../common/components';
import { document as documentApi } from '../../../../common/api';
import { DocumentItem } from './components';
import { BookCard } from '../../components';
import { goTo } from '../../../../history';

export class DocumentsSearch extends Component {
  searchApi = new InvenioSearchApi({
    url: documentApi.searchBaseURL,
    withCredentials: true,
  });
  state = { activeIndex: 0, isLayoutGrid: true };
  searchConfig = getSearchConfig('documents');

  toggleAccordion = (e, titleProps) => {
    const { index } = titleProps;
    const { activeIndex } = this.state;
    const newIndex = activeIndex === index ? -1 : index;
    this.setState({ activeIndex: newIndex });
  };

  renderAccordionAggregations = (
    title,
    resultsAggregations,
    aggregations,
    customProps
  ) => {
    const { activeIndex } = this.state;

    return resultsAggregations !== undefined ? (
      <Accordion as={Menu} vertical>
        <Menu.Item>
          <Accordion.Title
            content={title}
            index={customProps.index}
            active={activeIndex === customProps.index}
            onClick={this.toggleAccordion}
          />
          <Accordion.Content
            active={activeIndex === customProps.index}
            content={aggregations}
          />
        </Menu.Item>
      </Accordion>
    ) : null;
  };

  renderSearchBar = (_, queryString, onInputChange, executeSearch) => {
    return (
      <DocumentsSearchBar
        currentQueryString={queryString}
        onInputChange={onInputChange}
        executeSearch={executeSearch}
        placeholder={'Search for records...'}
      />
    );
  };

  renderResultsLayoutOptions = () => {
    const toggleLayout = () => {
      this.setState({ isLayoutGrid: !this.state.isLayoutGrid });
    };
    return (
      <Button.Group basic icon>
        <Button disabled={this.state.isLayoutGrid} onClick={toggleLayout}>
          <Icon name="grid layout" />
        </Button>
        <Button disabled={!this.state.isLayoutGrid} onClick={toggleLayout}>
          <Icon name="list layout" />
        </Button>
      </Button.Group>
    );
  };

  renderResultsGrid = results => {
    const cards = results.map(book => {
      return <BookCard key={book.metadata.pid} data={book} />;
    });
    return (
      <Card.Group doubling stackable itemsPerRow={4}>
        {cards}
      </Card.Group>
    );
  };

  renderResultsList = results => {
    return results.length ? (
      <div>
        {results.map(book => (
          <DocumentItem
            key={book.metadata.pid}
            data-test={book.metadata.pid}
            metadata={book.metadata}
            rowActionClickHandler={pid =>
              goTo(FrontSiteRoutes.documentDetailsFor(pid))
            }
          />
        ))}
      </div>
    ) : null;
  };

  renderEmptyResults = (queryString, resetQuery) => {
    return (
      <Segment placeholder textAlign="center">
        <Header icon>
          <Icon name="search" />
          No records found!
        </Header>
        <div className="empty-results-current">
          Current search "{queryString}"
        </div>
      </Segment>
    );
  };

  renderError = error => {
    return <IlsError error={error} />;
  };

  renderCount = totalResults => {
    return <div>{totalResults} results</div>;
  };

  renderAggregations = () => {
    const accordionPanels = this.searchConfig.AGGREGATIONS.map((agg, idx) => (
      <div className="aggregator" key={agg.field}>
        <Aggregator
          title={agg.title}
          field={agg.field}
          customProps={{ index: idx }}
          renderElement={this.renderAccordionAggregations}
        />
      </div>
    ));

    const cardPanels = this.searchConfig.AGGREGATIONS.map(agg => (
      <div className="aggregator" key={agg.field}>
        <Aggregator title={agg.title} field={agg.field} />
      </div>
    ));

    return (
      <div>
        <Responsive {...Responsive.onlyMobile}>{accordionPanels}</Responsive>
        <Responsive {...Responsive.onlyComputer}>{cardPanels}</Responsive>
      </div>
    );
  };

  renderHeader = () => {
    return (
      <Grid columns={3} verticalAlign="middle" stackable relaxed>
        <Grid.Column width={2}>{this.renderResultsLayoutOptions()}</Grid.Column>
        <Grid.Column width={3} textAlign="left">
          <Count renderElement={this.renderCount} />
        </Grid.Column>
        <Grid.Column width={6}>
          <Pagination />
        </Grid.Column>
        <Grid.Column width={5} textAlign="right">
          <ResultsSort searchConfig={this.searchConfig} />
        </Grid.Column>
      </Grid>
    );
  };

  renderFooter = () => {
    return (
      <Grid columns={3} verticalAlign="middle" stackable relaxed>
        <Grid.Column width={5} />
        <Grid.Column width={6}>
          <Pagination />
        </Grid.Column>
        <Grid.Column width={5} />
      </Grid>
    );
  };

  render() {
    const queryString = this.props.location.search;
    const requestForm = (
      <Link
        to={{
          pathname: FrontSiteRoutes.documentRequestForm,
          state: { queryString },
        }}
      >
        book request form
      </Link>
    );
    return (
      <ReactSearchKit searchApi={this.searchApi}>
        <Container className="documents-search-searchbar">
          <SearchBar renderElement={this.renderSearchBar} />
        </Container>

        <Grid
          columns={2}
          stackable
          relaxed
          className="documents-search-container"
        >
          <Grid.Column width={3}>{this.renderAggregations()}</Grid.Column>
          <Grid.Column width={13}>
            <ResultsLoader>
              <EmptyResults renderElement={this.renderEmptyResults} />
              <Error renderElement={this.renderError} />
              {this.renderHeader()}
              {this.state.isLayoutGrid ? (
                <ResultsGrid renderElement={this.renderResultsGrid} />
              ) : (
                <ResultsList renderElement={this.renderResultsList} />
              )}
              {this.renderFooter()}
              <Message icon color="yellow">
                <Icon name="info circle" />
                <Message.Content>
                  <Message.Header>
                    Couldn't find the book you were looking for?
                  </Message.Header>
                  Please fill in the {requestForm} to request a new book from
                  the library.
                </Message.Content>
              </Message>
            </ResultsLoader>
          </Grid.Column>
        </Grid>
      </ReactSearchKit>
    );
  }
}