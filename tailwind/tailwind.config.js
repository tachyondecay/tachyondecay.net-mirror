module.exports = {
  theme: {
    fontFamily: {
      sans: 'Oswald, Verdana, Arial, sans-serif',
      serif: '"EB Garamond", Garamond, Palatino, "Times New Roman", serif'
    },
    extend: {
      colors: {
        marble: {
          50: '#F8F7F7',
          100: '#E6E5E6',
          200: '#CFC9CD',
          300: '#B1A9AF',
          400: '#a0929b',
          500: '#95838F',
          600: '#7C6A76',
          700: '#60525C',
          800: '#3D343A',
          900: '#1C171A',
        }
      },
      fontSize: {
        '2xs': '.6rem',
      },
      typography: ({ theme }) => ({
        DEFAULT: {
          css: {
            fontFamily: theme('fontFamily.serif'),
            'a': {
              textDecorationThickness: '2px',
            },
            blockquote: {
              fontStyle: 'normal',
              fontWeight: 400,
            },
            'blockquote p:only-of-type': {
              textIndent: '0 !important',
            },
            'blockquote p:first-of-type::before': {
              content: ''
            },
            'blockquote p:last-of-type::after': {
              content: ''
            },
            h2: {
              marginBottom: '0.5em',
            }
          }
        },
        md: {
          css: {
            h2: {
              marginBottom: '0.5em',
            }
          }
        },
        lg: {
          css: {
            h2: {
              marginBottom: '0.5em',
            }
          }
        },
        marble: {
          css: {
            '--tw-prose-body': theme('colors.marble[700]'),
            '--tw-prose-headings': theme('colors.marble[700]'),
            '--tw-prose-lead': theme('colors.marble[600]'),
            '--tw-prose-links': theme('colors.red[900]'),
            '--tw-prose-bold': theme('colors.marble[900]'),
            '--tw-prose-counters': theme('colors.marble[600]'),
            '--tw-prose-bullets': theme('colors.marble[400]'),
            '--tw-prose-hr': theme('colors.marble[300]'),
            '--tw-prose-quotes': theme('colors.marble[900]'),
            '--tw-prose-quote-borders': theme('colors.pink[600]'),
            '--tw-prose-captions': theme('colors.marble[700]'),
            '--tw-prose-code': theme('colors.marble[900]'),
            '--tw-prose-pre-code': theme('colors.marble[100]'),
            '--tw-prose-pre-bg': theme('colors.marble[900]'),
            '--tw-prose-th-borders': theme('colors.marble[300]'),
            '--tw-prose-td-borders': theme('colors.marble[200]'),
            '--tw-prose-invert-body': theme('colors.marble[200]'),
            '--tw-prose-invert-headings': theme('colors.marble[200]'),
            '--tw-prose-invert-lead': theme('colors.marble[300]'),
            '--tw-prose-invert-links': theme('colors.white'),
            '--tw-prose-invert-bold': theme('colors.white'),
            '--tw-prose-invert-counters': theme('colors.marble[400]'),
            '--tw-prose-invert-bullets': theme('colors.marble[600]'),
            '--tw-prose-invert-hr': theme('colors.marble[700]'),
            '--tw-prose-invert-quotes': theme('colors.marble[100]'),
            '--tw-prose-invert-quote-borders': theme('colors.marble[700]'),
            '--tw-prose-invert-captions': theme('colors.marble[400]'),
            '--tw-prose-invert-code': theme('colors.white'),
            '--tw-prose-invert-pre-code': theme('colors.marble[300]'),
            '--tw-prose-invert-pre-bg': 'rgb(0 0 0 / 50%)',
            '--tw-prose-invert-th-borders': theme('colors.marble[600]'),
            '--tw-prose-invert-td-borders': theme('colors.marble[700]'),
            'blockquote:hover': {
              borderColor: theme('colors.amber.600')
            },
          },
        },
        slate: {
          css: {
            '--tw-prose-headings': theme('colors.sky[900]'),
            '--tw-prose-links': theme('colors.fuchsia[900]'),
            '--tw-prose-quote-borders': theme('colors.fuchsia[900]'),
            'blockquote:hover': {
              borderColor: theme('colors.sky.700')
            },
          }
        }
      }),
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
  safelist: [
    'aspect-video',
  ],
}
