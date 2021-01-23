let apiReport = document.getElementById('api-report');
let apiData;
const template = document.getElementById('template').innerHTML;

function displayReport(date) {
    // Loop through apiData to find the right data
    let result;
    for(const day of apiData) {
        if(day.date == date) {
            result = day;
            for(const r in result) {
                if(!result[r]) {
                    result[r] = "N/A";
                }
            }
            break;
        }
    }
    if(result) {
        apiReport.innerHTML = Mustache.render(template, result);
    } else {
        apiReport.innerHTML = 'No data found for this date.';
    }
}


date_input = document.getElementById('date');
date_input.addEventListener('change', e => displayReport(e.target.value));

// Set default date
if(!date_input.value) {
    today = dayjs().format('YYYY-MM-DD');
    date_input.value = today;
}

// Load data
fetch('https://cors-anywhere.herokuapp.com/https://api.covid19tracker.ca/reports/regions/3562')
    .then(response => response.json())
    .then(data => {
        apiData = data.data;
        displayReport(date_input.value);
    })
    .catch(error => {
        console.log(error);
        apiReport.innerText = "Error loading data.";
    });
