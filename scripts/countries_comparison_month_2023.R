comext_bovine_2023_month <- function(month){
 # return(class(month))
  library(data.table)
  month2 <- as.numeric(month)
  month_name <-deparse(substitute(month2))

  my_data_path <- paste("N:/full2023",month, ".dat", sep="")
  function_data <- fread(my_data_path)
  function_data <-as.data.frame(function_data)
  
  
  library(dplyr)
  library(stringr)
  data_2 <- filter(function_data, DECLARANT_ISO %in% c("AT", "DE", "HU", "IT", "SK", "SI","CZ", "HR"), FLOW=="2", PRODUCT_NC %in% c("01022110", "01022130"))
  #FLOW 2 - export
  #TRADE_TYPE=="E" - outside of EU
  df_month <- aggregate(SUP_QUANTITY ~ DECLARANT_ISO + PARTNER_ISO, data_2, sum)
  colnames(df_month)[colnames(df_month) == "SUP_QUANTITY"] <- paste("quant",month_name,sep="")
  write.csv(df_year, paste("data",month_name,".csv", sep=""))
  df_month <<- df_month
  month_name<<-month_name
  data_cat<<-full_join(data_cat, df_year, by=c("PARTNER_ISO"="PARTNER_ISO", "PRODUCT_NC"="PRODUCT_NC"))
  
}

comext_bovine_2023_month("12")
df_2023_by_month <-df_month
comext_bovine_2023_month("11")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("10")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("09")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("08")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("07")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("06")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("05")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("04")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("03")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("02")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
comext_bovine_2023_month("01")
df_2023_by_month<- full_join(df_2023_by_month, df_month, by=c("PARTNER_ISO"="PARTNER_ISO", "DECLARANT_ISO"="DECLARANT_ISO") )
df_2023_by_month2<-df_2023_by_month
df_2023_by_month2[is.na(df_2023_by_month2)] <- 0
write.csv(df_2023_by_month2, paste("data2023bymonth.csv", sep=""))
