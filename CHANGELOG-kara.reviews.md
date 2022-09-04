# Changelog for Kara.Reviews

Welcome to the changelog for this site! This is mostly for my purposes, but 
it’s a fun Easter egg for the rest of you.

I update this whenever I make a larger change or set of changes, such as adding 
a new feature/page, or altering the structure or programming of the site 
significantly. Smaller changes will go unremarked upon here—if you are really 
curious, check out [the public repo on GitHub][github] for all my commits.


[github]: https://github.com/tachyondecay/tachyondecay.net-mirror


## 3.2 (2022-09-03)

Add a changelog to my sites!


## 3.1 (2022-07-05)

Add the ability to sort review search results by field. Append `?sortby=fieldname`
to the search URL, e.g. `?sortby=book_title`. Use the `reverse` parameter to 
change the sort order direction, e.g. `?sortby=book_title&reverse`


## 3.0 (2021-12-28)

Recreated the frontend design using Tailwind CSS. No serious design changes here 
except to the [review index][ri], which makes it a little easier to navigate.

[ri]: https://kara.reviews/


## 2.2 (2021-12-04)

StoryGraph is here!

### Frontend Features

* There is now a StoryGraph link (when one is available) at the bottom of each 
review.

### Backend Features

* Add a field to reviews for storing StoryGraph review link
* Add a “Copy to StoryGraph”


## 2.1 (2021-11-15)

Cover images are now processed by the Pillow library, which converts them to 
JPEGs and resizes them.


## 2.0 (2020-08-27)

Migration from SQLite to Postgres and significant backend refactoring.

### Backend Features

* Both sites now use Postgres instead of SQLite
* The database uses a joined inheritance model with a unified `Posts` table
shared by `Articles`, `Lists`, and `Reviews`
* The CMS now supports creating lists of articles or reviews (no frontend yet)
* Add a `--per-pass` option to the `reindex` command for efficiency


## 1.1 (2020-10-12)
Improvements to the search engine.

* Searches default to the book title unless modifiers are present
* Expose Whoosh’s modifier syntax to allow for more advanced searches.


## 1.0 (2020-08-18)

Launch of Kara.Reviews (see [my blog post][launch]).

### Frontend Features

* Browsing reviews from the homepage, via tags (“bookshelves”), or the 
review index
* Search
* OpenGraph tags for sharing reviews on social media

### Backend Features

* Writing reviews in the unified CMS
* Drafts
* Revision-tracking and autosaving
* Uploading covers directly into the CMS

[launch]: https://tachyondecay.net/blog/2020/08/announcing-kara-reviews/


*[CMS]: Content Management System
*[CSS]: Cascading Style Sheets