import React, { Component } from 'react';
import { Container, Grid, Segment, Icon, Header } from 'semantic-ui-react';
import {
  ReactSearchKit,
  SearchBar,
  ResultsList,
  ResultsLoader,
  EmptyResults,
  Error,
  Pagination,
  Count,
} from 'react-searchkit';
import { apiConfig } from '../../../common/api/base';
import { getSearchConfig } from '../../../common/config';
import {
  Error as IlsError,
  SearchBar as EItemsSearchBar,
  ResultsSort,
} from '../../../common/components';
import { eitem as eitemApi } from '../../../common/api';
import { ClearButton, NewButton } from '../components/buttons';
import { BackOfficeRoutes, openRecordEditor } from '../../../routes/urls';
import { ResultsList as EItemsResultsList } from './components';
import { goTo } from '../../../history';
import './EItemsSearch.scss';

export class EItemsSearch extends Component {
  searchConfig = getSearchConfig('eitems');

  renderSearchBar = (_, queryString, onInputChange, executeSearch) => {
    return (
      <EItemsSearchBar
        currentQueryString={queryString}
        onInputChange={onInputChange}
        executeSearch={executeSearch}
        placeholder={'Search for eitems'}
      />
    );
  };

  renderResultsList = results => {
    return (
      <div className="results-list">
        <EItemsResultsList
          results={results}
          viewDetailsClickHandler={row =>
            goTo(BackOfficeRoutes.eitemDetailsFor(row.ID))
          }
        />
      </div>
    );
  };

  renderEmptyResults = (queryString, resetQuery) => {
    return (
      <Segment placeholder textAlign="center">
        <Header icon>
          <Icon name="search" />
          No eitems found!
        </Header>
        <div className="empty-results-current">
          Current search "{queryString}"
        </div>
        <Segment.Inline>
          <ClearButton
            clickHandler={() => {
              resetQuery();
            }}
          />
          <NewButton
            text={'New eitem'}
            clickHandler={() => {
              openRecordEditor(eitemApi.url);
            }}
          />
        </Segment.Inline>
      </Segment>
    );
  };

  renderError = error => {
    return <IlsError error={error} />;
  };

  renderCount = totalResults => {
    return <div>{totalResults} results</div>;
  };

  renderHeader = () => {
    return (
      <Grid columns={3} verticalAlign="middle" stackable relaxed>
        <Grid.Column width={5} textAlign="left">
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
    return (
      <ReactSearchKit
        searchConfig={{
          ...apiConfig,
          url: eitemApi.url,
        }}
      >
        <Container className="eitems-search-searchbar">
          <SearchBar renderElement={this.renderSearchBar} />
        </Container>

        <Grid columns={2} stackable relaxed className="eitems-search-container">
          <Grid.Column width={16}>
            <ResultsLoader>
              <EmptyResults renderElement={this.renderEmptyResults} />
              <Error renderElement={this.renderError} />
              {this.renderHeader()}
              <ResultsList renderElement={this.renderResultsList} />
              {this.renderFooter()}
            </ResultsLoader>
          </Grid.Column>
        </Grid>
      </ReactSearchKit>
    );
  }
}
