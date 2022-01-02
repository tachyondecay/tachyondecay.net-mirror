module.exports = {
  presets: [
    require('./tailwind.config.js')
  ],
  content: [
    "./lemonade_soapbox/assets/js/*.js",
    "./lemonade_soapbox/templates/reviews/**/*.html",
    "./lemonade_soapbox/templates/macros.html",
  ],
}