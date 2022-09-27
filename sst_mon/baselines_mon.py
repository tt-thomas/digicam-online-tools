#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 29 12:15:04 2022

@author: zrdz
"""

import numpy as np
##import bokeh
# import pandas as pd
import os
from bokeh.io import curdoc
from glob import glob
from bokeh.plotting import figure
#from bokeh.models import CheckboxGroup, NumberFormatter, DataTable, TableColumn, Band,BoxAnnotation
from bokeh.models import Select, CustomJS, Div ,TextInput ,Panel,  Tabs, Button, ColumnDataSource
#from bokeh.models import BooleanFilter, GroupFilter, CDSView, Range1d, Span, HoverTool
from bokeh.layouts import layout

from datetime import datetime

from pkg_resources import resource_filename
from cts_core.camera import Camera
from digicampipe.instrument import geometry
from digicampipe.io.event_stream import event_stream, add_slow_data
import astropy.units as u

from my_bokeh import CameraDisplay #BokehPlot

class nsb_mon():
    def __init__(self,tel):
        
        self.tel = tel
        
        self.error_txt  = ""
        self.error_datasource = ColumnDataSource(data={'error_txt' : [""]})
        
        #self.data_dir = os.path.join("/mnt/"+"cs{}/raw/".format(tel))
        self.data_dir = os.path.join("/net/cs{}/data/raw/".format(tel))
        
        try:
            self.year_list = next(os.walk(self.data_dir))[1]
        except:
            self.year_list = ["No data"]

        
        
        ### CAM GEOM 
        digicam_config_file = resource_filename('digicampipe','tests/resources/camera_config.cfg')
        digicam = Camera(_config_file=digicam_config_file)
        self.geom = geometry.generate_geometry_from_camera(camera=digicam)
        self.geom.pix_area = np.ones(self.geom.n_pixels)*482.05 *u.mm**2 ## ??????
        self.geom.pixel_width = self.geom.pix_area**.5 *1.1#/(3**.5) ## ??????
        #self.geom.frame=??

        self.n_pixels = self.geom.n_pixels
        self.pixels   = np.arange(self.n_pixels)
        
        
        mon_data = {'baselines_mean' : np.zeros(self.n_pixels),
                    'baselines_std'  : np.zeros(self.n_pixels)}
                    
        self.baslines_datasource = ColumnDataSource(data=mon_data)
        
        hist_data = {'count': [], 'left': [], 'right': []}
        self.mean_hist_ds = ColumnDataSource(data=hist_data)
        self.std_hist_ds = ColumnDataSource(data=hist_data)
        
        
        self.month_list = []
        self.day_list   = []
        self.zfits_list = []
        
        ########################
        #### Error Div :: 
        ########################
        
        
        
        self.err_div = Div(
            text="",
            width=1000,
            height=20,
        )
        
        
        ########################
        #### Camera display :: 
        ########################
        
        self.cam_mean_display = CameraDisplay(geometry=self.geom,
                                        title="Mean baselines",
                                        image = np.zeros(self.n_pixels))
        self.cam_mean_display.add_colorbar()
            
        
        self.cam_std_display = CameraDisplay(geometry=self.geom,
                                        title="baselines st.d.",
                                        image = np.zeros(self.n_pixels))
        self.cam_std_display.add_colorbar()


        
        ###########################
        ## file selection wisgets
        ###########################
        DSW = 80
        self.select_year = Select(title="year", 
                             value="", 
                             options=self.year_list,
                             width=DSW)
        
        self.select_month = Select(title="month", 
                              value="", 
                              options=[],
                              width=DSW)

        self.select_day   = Select(title="Day", 
                              value="", 
                              options=[],
                              width=DSW)
        
        self.select_zfits   = Select(title="zfits files", 
                              value="", 
                              options=[],
                              width=DSW*6)
        
        
        self.update_button = Button(label="Show last file",
                                    button_type="success",
                                    width=DSW)
        
        
        #### Events
        ###########
        self.update_button.on_click(self.update_files)
        
        self.select_year.on_change ("value", self.load_months)
        self.select_month.on_change("value", self.load_days)
        self.select_day.on_change("value", self.load_zfitss)
        
        self.select_zfits.on_change("value",self.zfits_callback)
        
        # self.select_year.value = self.year_list[-1]
        
        self.h_means = self.make_hist(self.mean_hist_ds,"mean baselines","ADC")
        self.h_stds  = self.make_hist(self.std_hist_ds ,"baselines std","ADC")
        
        
        ##############
        ### LAYOUT
        ##############
        
        self.layout = layout([[self.select_year,
                               self.select_month,
                               self.select_day,
                               self.select_zfits,
                               self.update_button],
                               self.err_div,
                               [self.h_means, 
                                self.h_stds],
                               [self.cam_mean_display.figure,
                                self.cam_std_display.figure]],
                               )#sizing_mode='fixed')
        
        self.tab = Panel(child=self.layout,     title= "Telescope {}".format(self.tel))
        
    ###################
    ####### Callbacks
    ###################
    
    def zfits_callback(self,attr, old, new):
        self.load_mon_data()
        
    
    def load_months(self,attr, old, new):
        try:
            self.select_month.options = next(os.walk(os.path.join(self.data_dir,
                                                        self.select_year.value)))[1]
        except:
            self.select_month.options = ["no data"]
            
        self.select_month.value = self.select_month.options[-1]

        
    def load_days(self,attr, old, new):
        try:
            self.select_day.options = next(os.walk(os.path.join(self.data_dir,
                                                      self.select_year.value,
                                                      self.select_month.value)))[1]
        except:
            self.select_day.options = ["No data"]
            
        self.select_day.value = self.select_day.options[-1]

        
    def load_zfitss(self,attr, old, new):
        # try:
        #     self.select_zfits.options = next(os.walk(os.path.join(self.data_dir,
        #                                                 self.select_year.value,
        #                                                 self.select_month.value,
        #                                                 self.select_day.value,
        #                                                 'SST1M1')))[2]
        
        try:
            self.select_zfits.options = sorted(glob(os.path.join(self.data_dir,
                                                        self.select_year.value,
                                                        self.select_month.value,
                                                        self.select_day.value,
                                                        'SST1M*/*.fz'))
                                               )[:-1]
            
        except:
            self.select_zfits.options = ["No data"]
            
        if len(self.select_zfits.options) == 0:
            self.select_zfits.options = ["No data"]
            
        self.select_zfits.value = self.select_zfits.options[-1]
        
        
    ## update button callback
    def update_files(self):
        self.load_zfitss("","","")

    #################
    #### Load data
    #################
    
    def load_mon_data(self):
        # file_path = os.path.join(self.data_dir,
        #                          self.select_year.value,
        #                          self.select_month.value,
        #                          self.select_day.value,
        #                          'SST1M2',
        #                          self.select_zfits.value)
        n_mon_evt = 0
        
        try:
            data_stream = event_stream(
                filelist=[self.select_zfits.value],
                max_events=1000
                )
            baselines_mean = np.zeros(self.n_pixels)
            baselines_std  = np.zeros(self.n_pixels)
            
    
            print('loading', self.select_zfits.value)
            for ii,event in enumerate(data_stream):
                # for tel in event.r0.tels_with_data:
                    tel = 22
                    r0data = event.r0.tel[tel]
                    if r0data._camera_event_type.value==8:
                        n_mon_evt      += 1
                        baselines_mean += r0data.adc_samples.mean(axis=1)
                        baselines_std  += r0data.adc_samples.std(axis=1)
                        
                        if n_mon_evt >100:
                            break
        except:
            self.err_div.text='<p style="color:red">Error : \
                wasn\'t able to read  file {}</p>'.format(self.select_zfits.value)
            return
        
        if n_mon_evt == 0:
            ## err no baselines
            self.err_div.text='<p style="color:red">Error : \
                No baselines events found in file {}</p>'.format(self.select_zfits.value)

            return
        self.err_div.text=""
        
        baselines_mean = baselines_mean / n_mon_evt
        baselines_std  = baselines_std  / n_mon_evt
        
        mon_data = {'baselines_mean' : baselines_mean,
                    'baselines_std'  : baselines_std}
                    
        self.baslines_datasource.data=mon_data
        
        h, edges = np.histogram( baselines_mean, bins=100 )
        hist_data = {'count': h, 'left': edges[:-1], 'right': edges[1:]}
        self.mean_hist_ds.data = hist_data


        h,  edges  = np.histogram( baselines_std,  bins=100 )
        hist_data = {'count': h, 'left': edges[:-1], 'right': edges[1:]}
        self.std_hist_ds.data = hist_data
        
        # print(self.mean_hist_ds.data)
        
        
        self.cam_std_display.datasource.data['values'] = mon_data['baselines_std']
        self.cam_std_display.rescale()
        ## self.cam_std_displayset_limits_minmax(
                ## mon_data['baselines_std'][mon_data['baselines_std']>0].min(),
                ## mon_data['baselines_std'].max())
        self.cam_mean_display.datasource.data['values'] = mon_data['baselines_mean']
        self.cam_mean_display.rescale()
        
    def make_hist(self,arr_src,title,x_axis_label):
        p = figure(plot_width = 600, 
           plot_height = 500,
           title = title,
           x_axis_label = x_axis_label, 
           y_axis_label = 'Count')

        # Add a quad glyph with source this time
        p.quad(bottom=0, 
               top='count', 
               left='left', 
               right='right', 
               source=arr_src,
               fill_color='green',
               # hover_fill_alpha=0.7,
               # hover_fill_color='blue',
               line_color='black')
        
        # Add style to the plot
        p.title.align = 'center'
        p.title.text_font_size = '18pt'
        p.xaxis.axis_label_text_font_size  = '12pt'
        p.xaxis.major_label_text_font_size = '12pt'
        p.yaxis.axis_label_text_font_size  = '12pt'
        p.yaxis.major_label_text_font_size = '12pt'
        
        return p



#################################################################
##############    CREATE HTML CONTENT          ##################
#################################################################

if True:

    div1 = Div(
        text="""
            <h1>SST-1M baseline Viewer 1.1</h1>
            <img align="right" src='sst_mon/static/logo.png' alt='logox'>
            """,
        width=5000,
        height=100,
    )
  # <img align="right" src="logo.png" alt="logo">
    mon_cs2 = nsb_mon(2)
    try:
        mon_cs2.select_year.value = mon_cs2.year_list[-1]
    except:
        mon_cs2.err_div.text= "ERROR : Did not found any data. (Data Disk not mounted ?)"
    
    mon_cs1 = nsb_mon(1)
    try:
        mon_cs1.select_year.value = mon_cs2.year_list[-1]
    except:
        mon_cs1.err_div.text= "ERROR : Did not found any data. (Data Disk not mounted ?)"
        
    
    # mon_cs2.p = mon_cs2.make_hist(mon_cs2.mean_hist_ds,"mean baselines","mean baseline")
    # mon_cs2. load_mon_data()
    
    
    tab_cs1     = Panel(child=mon_cs1.layout,     title= "Telescope 1")
    tab_cs2     = Panel(child= mon_cs2.layout,    title= "Telescope 2")
    
    tabs = Tabs(tabs=[mon_cs1.tab, mon_cs2.tab])
    
    full_layout = layout([[div1],[tabs]])
    
    curdoc().add_root(full_layout)
    
    
