#!/usr/bin/env python3
# Configurations to run the program properly

# Account Settings
#
# Leanote host(Default: https://leanote.com)
host = ''
# Your email
email = ''
# Your password
pwd = ''

# Basic Output Settings
#
# Path to save your notes
output_path = './Leanote'
# Only output blog note if True
only_blog = False

# Output meta data
output_meta = False

# Image Output Settings
#
# Save notes' images if True
localize_image = True
# Path to save notes' images
img_path = './.images'
# Path that image links references
# For instance:
#   - Original link: ![](https://web.image.com/my_image.png)
#   - If set this var: ![](/images/my_image.png)
img_link_path = './.images'
img_external = False

# Save attachment
localize_attach = True
#
attach_path = './.attachments'
attach_link_path = './.attachments'

# Force to save images if True, even though already downloaded
forced_save = True
