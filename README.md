# Lemonade Soapbox

This is the codebase that powers my two personal sites, [tachyondecay.net](https://tachyondecay.net/) and [kara.reviews](https://kara.reviews/). The former is mostly a blog, and the latter is a book review website. As a result, this project has transformed over the years through feature creep from a simple blog to something closer to a CMS.

Why "Lemonade Soapbox"? The soapbox is a reference to the app’s origins as blog software—a soapbox being something that people would stand on to give speeches in the old days. The "lemonade" is an homage to the predecessor of this app, which I wrote from scratch in PHP. I called it "VSNS" for "Very Simple News System," and a later version became "VSNS Lemon."

## Credits
This app is built mostly from [Flask](https://flask.palletsprojects.com) along with Sass to power my CSS, and a frightening mixture of jQuery and vanilla JS (I am slowly weaning myself off jQuery).

The revision-tracking feature for posts uses [Google's Diff Match Patch](https://github.com/google/diff-match-patch) library.

## Licence/Usage
If you are reading this, you’re seeing the public mirror repo I set up for this code. I keep the authoritative repo private because this lets me maintain issues and projects privately.

I'm making this code available publicly largely because it's easier for me to reference it that way when helping others. If you find something in this codebase that works for you, that's awesome and I want you to be able to steal it and make it your own!

That being said, **this is a specialized codebase, *not* a general blog/CMS package**. I have opinions on how I want my blog/CMS to work, and I have done a lot of work to make this app serve 2 websites with a unified administrative UI. So everything is highly optimized towards that goal. Please do not clone this repo thinking you can deploy it easily to get your own blog software. There are probably many greater solutions.

That being said, if you're digging deep and you happen to run across an issue, please [@ me on Twitter](https://twitter.com/tachyondecay) or email me at <kara@tachyondecay.net>.