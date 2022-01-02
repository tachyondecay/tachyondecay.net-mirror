/*
 * Lightbox
 */

removeLightbox = function() {
	document.getElementById('lightbox').remove();
	document.querySelector('body').classList.remove('overflow-hidden');
}

const lightboxes = document.querySelectorAll('.js-lightbox a');
lightboxes.forEach(elem => {
	const images = elem.getElementsByTagName('img');
	if(images.length == 1) {
		elem.addEventListener('click', e => {
			e.preventDefault();
			const overlay = document.createElement('div');
			overlay.setAttribute('id', 'lightbox');
			const overlay_classes = [
				"flex", "justify-center", "items-center",
				"fixed", "top-0", "left-0", "right-0", "bottom-0", "z-50",
				"p-3", "md:p-6", "lg:p-12",
				"bg-slate-900/75"
			];
			overlay.classList.add(...overlay_classes);

			const image = document.createElement('img');
			image.setAttribute('src', images[0].src);
			image.classList.add("max-w-screen", "max-h-screen");
			overlay.appendChild(image);

			overlay.addEventListener('click', removeLightbox);
			const body = document.querySelector('body');
			body.classList.add('overflow-hidden');
			body.appendChild(overlay);
		});
	}
});

if(lightboxes.length > 0) {
	document.addEventListener('keydown', e => {
		if(e.keyCode == 27) {
			removeLightbox();
		}
	})
}


/*
 * Name pronunciation on homepage
 */
const audio = document.getElementById("pronunciation");
if(audio) {
	audio.controls = false;
	const trigger = document.getElementById("pronunciation-trigger");
	trigger.addEventListener("click", e => {
		audio.play();
	});
}


/*
 * Recent podcast episodes on homepage
 */
const podcasts = document.getElementById("latest-episodes");
if(podcasts) {
	const feeds = [
		"https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Flisten.wejustliketotalk.com%2Ffeed.xml&api_key=vyvifcf1fmbxjbeka6f8bwslbfuzosdjnv7lqwdz&count=1",
		"https://api.rss2json.com/v1/api.json?rss_url=https%3A%2F%2Flisten.prophecygirls.ca%2Ffeed.xml&api_key=vyvifcf1fmbxjbeka6f8bwslbfuzosdjnv7lqwdz&count=1"
	];
	const fmt = new Intl.DateTimeFormat('en', { month: 'long', day: '2-digit', year: 'numeric' });
    const template = document.getElementById('ep-template').innerHTML;
    const customTags = ["[{", "}]"];
    Mustache.tags = customTags;
    Mustache.parse(template);

	feeds.forEach(rssURL => {
		fetch(rssURL)
		    .then(response => response.json())
		    .then(data => {
		    	console.log(data);
		        const expr = /<p>(.*?)<\/p>/;
		        data.items.forEach((ep, i) => {
		            let pubDate = new Date(ep.pubDate);
		            let render = Mustache.render(template, {
		                title: ep.title,
		                link: ep.link,
		                dateTime: pubDate,
		                pubDate: fmt.format(pubDate),
		                id: i,
		                type: ep.enclosure.type,
		                src: ep.enclosure.link,
		                description: expr.exec(ep.description)[1],
		                thumbnail: ep.thumbnail,
		                podcastSite: data.feed.link,
		                podcastTitle: data.feed.title,
		            });
		            podcasts.innerHTML += render;
		            podcasts.parentNode.classList.remove("hidden");
		        });

		        // const players = Plyr.setup('.player');
		    });
	});
}